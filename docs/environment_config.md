# CADRender 环境配置

新环境按本文配置即可跑校准与 Blender 管线。配置分三层（优先级从高到低）：

1. **已导出的系统/会话环境变量**（不覆盖）
2. **仓库根目录 `.env`**（`load_calibration_env` 自动读取）
3. **本文 `cadrender-env` 代码块**（默认值与团队模板）

## 一键加载

在仓库根目录执行：

```powershell
# PowerShell：加载到当前会话
.\scripts\load_calibration_env.ps1

# 或写入 .env 后手动编辑密钥
python scripts\load_calibration_env.py --write .env
```

校准入口 `calibrate.py` 启动时会**自动**调用同一加载逻辑（无需先手动 export）。

```powershell
cd blenderworker
$env:PYTHONPATH = "src"
python scripts\calibrate.py --scope texture --finish-id outdoor_sand --help
```

## 变量说明

### VLM（类目校准 Stage 1/4、纹理 `--use-vlm`）

| 变量 | 说明 | 默认 |
|------|------|------|
| `CADRENDER_VLM_API_KEY` | 通义 DashScope API Key（`sk-` 开头） | 空（未设则禁用 VLM） |
| `CADRENDER_VLM_MODEL` | 多模态模型 | `qwen3.5-flash` |
| `CADRENDER_VLM_API_BASE` | OpenAI 兼容端点 | `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions` |

> 同一 DashScope Key **不能**用于 DeepSeek 端点。Claude Code 代理见 [CLAUDE_PROXY_STARTUP.md](./CLAUDE_PROXY_STARTUP.md)。

### Blender TCP

| 变量 | 说明 | 默认 |
|------|------|------|
| `BLENDER_HOST` | BlenderControlService 地址 | `127.0.0.1` |
| `BLENDER_PORT` | TCP 端口 | `19876` |
| `BLENDER_MCP_ROOT` | blenderworker 根路径（可选） | 自动推断 |
| `CADRENDER_PRESETS_DIR` | 预设 JSON 目录（可选） | `blenderworker/blender_mcp_presets` |

### 校准与 HuggingFace 缓存

| 变量 | 说明 | 默认 |
|------|------|------|
| `HF_HUB_OFFLINE` | 离线 HF，避免校准时联网拉模型 | `1` |
| `TRANSFORMERS_CACHE` | HF 缓存目录 | `blenderworker/blender_mcp_presets/hf_cache`（`calibrate.py` 自动设） |
| `CADRENDER_CAL_QUALITY` | 校准渲染质量档位 | `preview` |

### Claude Code 代理（与 VLM 无关）

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek Key（仅 `deepseek_proxy.py`） |
| `DEEPSEEK_BASE` | DeepSeek Anthropic 兼容基址 |
| `PROXY_PORT` | 本机代理端口 |

见 `.env.example` 与 [CLAUDE_PROXY_STARTUP.md](./CLAUDE_PROXY_STARTUP.md)。

---

## 机器可读配置块

下方 `cadrender-env` 块由 `scripts/load_calibration_env.py` 解析。**修改默认值请改此块**，然后重新加载或重跑 `calibrate.py`。

```cadrender-env
# ── VLM：通义 DashScope（类目/纹理 VLM 评分）──
CADRENDER_VLM_API_KEY=sk-your-dashscope-key
CADRENDER_VLM_MODEL=qwen3.5-flash
CADRENDER_VLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions

# ── Blender TCP ──
BLENDER_HOST=127.0.0.1
BLENDER_PORT=19876

# ── 校准 / HF 缓存 ──
HF_HUB_OFFLINE=1
CADRENDER_CAL_QUALITY=preview

# ── 可选：覆盖预设目录（留空则使用 blender_mcp_presets）──
# CADRENDER_PRESETS_DIR=

# ── Claude 代理（copy .env.example；通常不与 VLM 共用同一 Key）──
# DEEPSEEK_API_KEY=sk-your-deepseek-key
# DEEPSEEK_BASE=https://api.deepseek.com/anthropic
# PROXY_PORT=8099
```

## 纹理校准示例（outdoor_sand）

```powershell
cd blenderworker
.\..\scripts\load_calibration_env.ps1   # 或已配置 .env

$env:PYTHONPATH = "src"
python scripts\calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference outputs/yili_crops/outdoor_sand_crop.png `
  --use-vlm --texture-trials 30 --no-auto-write
```

参考图需先执行 `scripts/crop_yili_references.py`（依赖 `outputs/蚁力色卡/`）。

## 相关文档

- [校准管线设计](./calibration_pipeline_design.md)
- [材质校准指南](./material_calibration_guide.md)
- [纹理校准设计](./texture_calibration_design.md)
- [类目校准指南](./category_calibration_guide.md)
