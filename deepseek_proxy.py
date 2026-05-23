"""Local proxy: Claude Code → DeepSeek Anthropic-compatible API.

Claude Code (~/.claude/settings.json):
  ANTHROPIC_BASE_URL = http://localhost:8099
  ANTHROPIC_API_KEY  = <DeepSeek key>   (do NOT set ANTHROPIC_AUTH_TOKEN)
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

DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE", "https://api.deepseek.com/anthropic").rstrip("/")
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


def _upstream_headers(request: Request) -> dict:
    key = request.headers.get("x-api-key") or API_KEY
    h = {
        "Content-Type": request.headers.get("content-type", "application/json"),
        "x-api-key": key,
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
    }
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


async def _proxy_request(method: str, path: str, body: bytes, request: Request) -> Response:
    url = f"{DEEPSEEK_BASE}/{path.lstrip('/')}"
    headers = _upstream_headers(request)
    log.info("%s %s", method, path)

    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await CLIENT.request(method, url, content=body, headers=headers)
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


async def _proxy_stream(method: str, path: str, body: bytes, request: Request) -> Response:
    url = f"{DEEPSEEK_BASE}/{path.lstrip('/')}"
    headers = _upstream_headers(request)
    log.info("%s %s (stream)", method, path)

    try:
        req = CLIENT.build_request(method, url, content=body, headers=headers)
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

    async def forward():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
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
    if _wants_stream(path, body, request):
        return await _proxy_stream(request.method, path, body, request)
    return await _proxy_request(request.method, path, body, request)


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

    log.info("DeepSeek proxy http://127.0.0.1:%s → %s (trust_env=False)", PROXY_PORT, DEEPSEEK_BASE)
    uvicorn.run(app, host="127.0.0.1", port=PROXY_PORT, log_level="info")


if __name__ == "__main__":
    main()
