"""Local proxy: Claude Code → DeepSeek (Anthropic-compatible + multimodal).

Claude Code (~/.claude/settings.json):
  ANTHROPIC_BASE_URL = http://localhost:8099
  ANTHROPIC_API_KEY  = <DeepSeek key>   (do NOT set ANTHROPIC_AUTH_TOKEN)

Multimodal: converts Anthropic type:image blocks to OpenAI image_url format
when needed, and routes to DeepSeek's native /v1/chat/completions endpoint
(which supports vision) when images are present.
"""
from __future__ import annotations

import json
import logging
import os
import sys

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger("deepseek-proxy")

DS_ANTHROPIC_BASE = os.getenv("DEEPSEEK_ANTHROPIC_BASE", "https://api.deepseek.com/anthropic").rstrip("/")
DS_CHAT_BASE = os.getenv("DEEPSEEK_CHAT_BASE", "https://api.deepseek.com/v1").rstrip("/")
API_KEY = os.getenv("DEEPSEEK_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
PROXY_PORT = int(os.getenv("PROXY_PORT", "8099"))
MAX_RETRIES = 2
RETRY_DELAY_MS = [1000, 3000]

# Do not use Windows/system HTTP_PROXY — it often breaks localhost → internet.
CLIENT = httpx.AsyncClient(
    timeout=httpx.Timeout(600.0, connect=30.0, pool=30.0),
    limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
    trust_env=False,
    proxy=None,
)


# ── Message format converters (Anthropic ↔ OpenAI) ──────────────────────────

def _has_image_blocks(messages: list) -> bool:
    """Check if any message contains image content blocks."""
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "image":
                    return True
    return False


def _msgs_to_openai(messages: list) -> list:
    """Convert Anthropic message list to OpenAI /chat/completions format."""
    out = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        text_parts: list[str] = []
        for block in content:
            t = block.get("type")
            if t == "text":
                text_parts.append(block.get("text", ""))
            elif t == "image":
                src = block.get("source", {})
                data_uri = f"data:{src.get('media_type','image/png')};base64,{src.get('data','')}"
                text_parts.append(f"![image]({data_uri})")
            elif t == "tool_use":
                # Anthropic tool_use → OpenAI tool_call
                out.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"], ensure_ascii=False),
                        },
                    }],
                })
                return out  # tool_use is a separate assistant message
            elif t == "tool_result":
                tool_use_id = block.get("tool_use_id", "")
                result_content = block.get("content", "")
                if isinstance(result_content, list):
                    texts = [b["text"] for b in result_content if b.get("type") == "text"]
                    result_content = "\n".join(texts)
                out.append({
                    "role": "tool",
                    "tool_call_id": tool_use_id,
                    "content": str(result_content),
                })
                return out
        out.append({"role": role, "content": "\n".join(text_parts).strip()})
    return out


def _anthropic_remove_thinking(data: dict) -> dict:
    """Remove thinking blocks from Anthropic response."""
    if "content" in data and isinstance(data["content"], list):
        data["content"] = [b for b in data["content"] if b.get("type") != "thinking"]
    return data


def _openai_to_anthropic_msg(data: dict) -> dict:
    """Convert single OpenAI /chat/completions response → Anthropic message."""
    choice = data["choices"][0]
    msg = choice.get("message", {})
    finish = choice.get("finish_reason")

    content = []
    msg_content = msg.get("content")
    if msg_content:
        content.append({"type": "text", "text": msg_content})

    for tc in msg.get("tool_calls", []):
        content.append({
            "type": "tool_use",
            "id": tc["id"],
            "name": tc["function"]["name"],
            "input": json.loads(tc["function"]["arguments"]),
        })

    stop_map = {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "length": "max_tokens",
    }

    return {
        "id": data.get("id", ""),
        "type": "message",
        "role": msg.get("role", "assistant"),
        "content": content,
        "model": data.get("model", ""),
        "stop_reason": stop_map.get(finish),
        "stop_sequence": None,
        "usage": {
            "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": data.get("usage", {}).get("completion_tokens", 0),
        },
    }


def _make_anthropic_body(body: dict, force_anthropic: bool = False) -> dict:
    """Convert an Anthropic-format request body to OpenAI format if images present.

    Returns dict with keys:
      - use_openai (bool): whether conversion was done
      - body: the (possibly converted) body dict
    """
    messages = body.get("messages", [])
    if not _has_image_blocks(messages):
        return {"use_openai": False, "body": body}

    if force_anthropic:
        log.info("Image blocks detected but using Anthropic endpoint for Claude compatibility")
        return {"use_openai": False, "body": body}

    log.info("Image blocks detected → converting to OpenAI format")
    oai_messages = _msgs_to_openai(messages)

    oai_body = {
        "model": "deepseek-chat",
        "messages": oai_messages,
        "max_tokens": body.get("max_tokens", 4096),
        "stream": body.get("stream", False),
    }
    log.debug("Converted Anthropic image request to OpenAI body model=%s stream=%s", oai_body["model"], oai_body["stream"])
    # pass through supported top-level fields
    for k in ("temperature", "top_p", "stop", "presence_penalty", "frequency_penalty"):
        if k in body:
            oai_body[k] = body[k]

    return {"use_openai": True, "body": oai_body}


# ── Streaming SSE converters ────────────────────────────────────────────────

def _transform_openai_sse(line: str) -> str | None:
    """Convert a single OpenAI SSE line to Anthropic SSE format.

    Returns the transformed line, or None to skip, or a list of lines to emit.
    """
    line = line.rstrip("\n")
    if not line.startswith("data: "):
        return line  # pass through (e.g. ":" keepalive comments)

    payload = line.removeprefix("data: ").strip()
    if payload == "[DONE]":
        return None  # skip — Anthropic uses event: message_stop instead

    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return line

    choices = chunk.get("choices", [])
    if not choices:
        return None

    delta = choices[0].get("delta", {})
    finish = choices[0].get("finish_reason")

    # content block start
    if delta.get("content") and delta.get("content") != "":
        # emit block start if first content
        return f"data: {json.dumps({'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}})}\n\ndata: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': delta['content']}})}"

    if delta.get("tool_calls"):
        # tool call
        tc = delta["tool_calls"][0]
        idx = tc.get("index", 0)
        func = tc.get("function", {})
        if func.get("name"):
            return f"data: {json.dumps({'type': 'content_block_start', 'index': idx, 'content_block': {'type': 'tool_use', 'id': tc.get('id', ''), 'name': func['name'], 'input': ''}})}"
        if func.get("arguments"):
            return f"data: {json.dumps({'type': 'content_block_delta', 'index': idx, 'delta': {'type': 'input_json_delta', 'partial_json': func['arguments']}})}"
        return None

    if finish == "tool_calls":
        return f"data: {json.dumps({'type': 'content_block_stop', 'index': 0})}"

    if finish == "stop":
        # Emit stop markers
        lines = [
            json.dumps({"type": "content_block_stop", "index": 0}),
            json.dumps({"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": chunk.get("usage", {}).get("completion_tokens", 0)}}),
        ]
        return f"data: {lines[0]}\n\ndata: {lines[1]}"

    if finish:
        return f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': finish, 'stop_sequence': None}, 'usage': {'output_tokens': chunk.get('usage', {}).get('completion_tokens', 0)}})}"

    return None


def _filter_anthropic_sse(line: str) -> str | None:
    """Filter out thinking blocks from Anthropic SSE streams."""
    line = line.rstrip("\n")
    if not line.startswith("data: "):
        return line
    
    payload = line.removeprefix("data: ").strip()
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError:
        return line
    
    # Skip thinking content blocks
    if chunk.get("type") in ("content_block_start", "content_block_delta"):
        content_block = chunk.get("content_block", {})
        if content_block.get("type") == "thinking":
            return None
        delta = chunk.get("delta", {})
        if delta.get("type") == "thinking_delta":
            return None
    
    return line


async def _forward_openai_stream(resp: httpx.Response):
    """Read OpenAI SSE stream and yield Anthropic-format SSE chunks."""
    # Emit start event
    yield b"event: message_start\n"
    yield b"data: " + json.dumps({"type": "message_start", "message": {"id": "", "type": "message", "role": "assistant", "content": [], "model": "", "stop_reason": None, "stop_sequence": None, "usage": {}}}).encode() + b"\n\n"

    buffer = ""
    async for raw in resp.aiter_bytes():
        buffer += raw.decode("utf-8", errors="replace")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            transformed = _transform_openai_sse(line)
            if transformed is None:
                continue
            yield b"event: content_block\n"
            yield transformed.encode() + b"\n\n"

    # Emit stop event
    yield b"event: message_stop\n"
    yield b"data: {}\n\n"

    await resp.aclose()


def _is_deepseek_error(data: dict) -> bool:
    return "error" in data and "type" not in data


def _normalize_error(data: dict, status_code: int) -> JSONResponse:
    ds_err = data["error"]
    msg = ds_err.get("message", str(status_code))
    err_type = ds_err.get("type", "api_error")
    log.error("DeepSeek %d — %s", status_code, msg[:200])
    return JSONResponse(
        status_code=status_code,
        content={"type": "error", "error": {"type": err_type, "message": msg}},
    )


def _upstream_headers(request: Request, openai: bool = False) -> dict:
    key = request.headers.get("x-api-key") or API_KEY
    h: dict[str, str] = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    if not openai:
        # Anthropic endpoint needs additional headers
        h["x-api-key"] = key
        h["anthropic-version"] = request.headers.get("anthropic-version", "2023-06-01")
        beta = request.headers.get("anthropic-beta")
        if beta:
            h["anthropic-beta"] = beta
    return h


def _wants_stream(path: str, body: bytes, request: Request) -> bool:
    if path.endswith("/stream"):
        return True
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept or "application/x-ndjson" in accept:
        return True
    if body:
        try:
            payload = json.loads(body)
            if payload.get("stream"):
                return True
        except json.JSONDecodeError:
            pass
    return False


async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "proxy": "deepseek", "port": PROXY_PORT})


def _parse_json_body(body: bytes) -> dict:
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        log.error("Failed to parse incoming JSON body: %s", e)
        raise


async def _proxy_request(method: str, path: str, body: bytes, request: Request, headers_override: dict | None = None) -> Response:
    try:
        raw_body = _parse_json_body(body)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"type": "error", "error": {"type": "invalid_request_error", "message": "Request body is not valid JSON."}},
        )
    force_anthropic = path.startswith("v1/messages") or path.endswith("/messages")
    info = _make_anthropic_body(raw_body, force_anthropic=force_anthropic)
    use_openai = info["use_openai"]

    if use_openai:
        base = DS_CHAT_BASE
        upstream_path = "chat/completions"
        upstream_body = json.dumps(info["body"], ensure_ascii=False).encode()
        log.info("%s %s → OpenAI vision endpoint", method, path)
    else:
        base = DS_ANTHROPIC_BASE
        upstream_path = path
        upstream_body = body

    url = f"{base}/{upstream_path.lstrip('/')}"
    headers = _upstream_headers(request, openai=use_openai)
    if headers_override:
        # allow caller to force/patch headers (e.g. set Content-Type when coercing body)
        headers.update({k: v for k, v in headers_override.items() if v is not None})
    log.info("%s %s", method, upstream_path if not use_openai else "chat/completions")

    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            if use_openai:
                resp = await CLIENT.request(method, url, json=info["body"], headers=headers)
            else:
                resp = await CLIENT.request(method, url, content=upstream_body, headers=headers)
            raw = resp.content
            if not raw:
                return Response(status_code=resp.status_code)

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return Response(content=raw, status_code=resp.status_code)

            if resp.status_code >= 400:
                if _is_deepseek_error(data):
                    return _normalize_error(data, resp.status_code)
                return JSONResponse(content=data, status_code=resp.status_code)

            if use_openai:
                data = _openai_to_anthropic_msg(data)
            else:
                # Remove thinking blocks from Anthropic responses
                data = _anthropic_remove_thinking(data)
            return JSONResponse(content=data, status_code=resp.status_code)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_err = e
            log.warning("Attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES:
                import asyncio
                await asyncio.sleep(RETRY_DELAY_MS[attempt] / 1000.0)

    log.error("Upstream failed: %s", last_err)
    return JSONResponse(
        status_code=502,
        content={"type": "error", "error": {"type": "api_error", "message": str(last_err)}},
    )


async def _proxy_stream(method: str, path: str, body: bytes, request: Request, headers_override: dict | None = None) -> Response:
    try:
        raw_body = _parse_json_body(body)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"type": "error", "error": {"type": "invalid_request_error", "message": "Request body is not valid JSON."}},
        )
    force_anthropic = path.startswith("v1/messages") or path.endswith("/messages")
    info = _make_anthropic_body(raw_body, force_anthropic=force_anthropic)
    use_openai = info["use_openai"]

    if use_openai:
        base = DS_CHAT_BASE
        upstream_path = "chat/completions"
        upstream_body = json.dumps(info["body"], ensure_ascii=False).encode()
        log.info("%s %s → OpenAI vision endpoint (stream)", method, path)
    else:
        base = DS_ANTHROPIC_BASE
        upstream_path = path
        upstream_body = body

    url = f"{base}/{upstream_path.lstrip('/')}"
    headers = _upstream_headers(request, openai=use_openai)
    if headers_override:
        headers.update({k: v for k, v in headers_override.items() if v is not None})
    log.info("%s %s (stream)", method, upstream_path if not use_openai else "chat/completions")

    if use_openai:
        # Ensure stream=true in the body
        body_dict = info["body"]
        body_dict["stream"] = True
        upstream_body = json.dumps(body_dict, ensure_ascii=False).encode()
        # Keep explicit JSON content type so DeepSeek receives the request correctly.
        headers["Content-Type"] = "application/json"
        log.debug("OpenAI stream request model=%s stream=%s", body_dict.get("model"), body_dict.get("stream"))
        log.debug("Upstream OpenAI JSON headers=%s", headers)

    try:
        if use_openai:
            req = CLIENT.build_request(method, url, json=body_dict, headers=headers)
        else:
            req = CLIENT.build_request(method, url, content=upstream_body, headers=headers)
        resp = await CLIENT.send(req, stream=True)
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        log.error("Stream connect failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"type": "error", "error": {"type": "api_error", "message": str(e)}},
        )

    if resp.status_code >= 400:
        raw = await resp.aread()
        await resp.aclose()
        try:
            data = json.loads(raw)
            if _is_deepseek_error(data):
                return _normalize_error(data, resp.status_code)
        except json.JSONDecodeError:
            pass
        return Response(content=raw, status_code=resp.status_code)

    if use_openai:
        return StreamingResponse(
            _forward_openai_stream(resp),
            status_code=resp.status_code,
            media_type="text/event-stream",
        )

    async def forward():
        try:
            buffer = ""
            async for raw in resp.aiter_bytes():
                buffer += raw.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                       filtered = _filter_anthropic_sse(line)
                       if filtered is None:
                           continue
                    yield filtered.encode() + b"\n"
            # Flush remaining buffer
            if buffer:
                   filtered = _filter_anthropic_sse(buffer)
                   if filtered is not None:
                       yield filtered.encode()
        finally:
            await resp.aclose()

    return StreamingResponse(
        forward(),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "text/event-stream"),
    )


async def catch_all(request: Request) -> Response:
    path = request.url.path.lstrip("/")
    body = await request.body()
    # Log incoming method/headers (keep short) for debugging 415 issues
    ctype = request.headers.get("content-type", "")
    try:
        sample = body.decode("utf-8", errors="replace")[:200]
    except Exception:
        sample = "<binary>"
    log.info("Incoming %s %s Content-Type=%s body-start=%s", request.method, path, ctype, sample)

    # If body present but Content-Type isn't JSON, try to coerce simple text into
    # an Anthropic-style JSON envelope so DeepSeek receives valid JSON instead of
    # raw text (common when clients send plain text like '你好'). We set a
    # headers_override so upstream sees application/json.
    headers_override = None
    if body and "application/json" not in ctype.lower():
        # If body doesn't look like JSON, wrap it as a simple Anthropic message
        text_try = None
        try:
            text_try = body.decode("utf-8")
        except Exception:
            text_try = None

        if text_try is not None and not text_try.lstrip().startswith(("{", "[")):
            coerced = {"messages": [{"role": "user", "content": text_try}]}
            body = json.dumps(coerced, ensure_ascii=False).encode()
            headers_override = {"Content-Type": "application/json"}
            log.info("Coerced non-JSON body to JSON envelope for path=%s", path)

    if _wants_stream(path, body, request):
        return await _proxy_stream(request.method, path, body, request, headers_override=headers_override)
    return await _proxy_request(request.method, path, body, request, headers_override=headers_override)


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/{path:path}", catch_all, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
    ],
)


def main() -> None:
    if not API_KEY:
        log.error("Set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY before starting.")
        sys.exit(1)
    import uvicorn

    log.info("DeepSeek proxy http://127.0.0.1:%s → %s / %s (trust_env=False)", PROXY_PORT, DS_ANTHROPIC_BASE, DS_CHAT_BASE)
    uvicorn.run(app, host="127.0.0.1", port=PROXY_PORT, log_level="info")


if __name__ == "__main__":
    main()
