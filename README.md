# CADRender: Distributed AI-Driven 3D SaaS Platform

通过 LLM 意图解析与分布式 Blender 渲染，实现从「自然语言 / 场景预设」到电商产品图的自动化流水线。

## 架构

```
renderui (React)
    → blenderserver (FastAPI, Claude API 可选)
        → blenderworker worker_main.py
            → Blender TCP :19876 (BlenderControlService)
```

| 模块 | 角色 |
|------|------|
| [blenderserver](./blenderserver) | SaaS 中台：任务队列、上传、LLM → Intent JSON、Worker 回调 |
| [blenderworker](./blenderworker) | Blender 执行内核：TCP 控制服务 + 电商棚拍 `core/` |
| [renderui](./renderui) | Web 前端 |

**说明**：项目已不再使用 MCP（Model Context Protocol）。Blender 与 worker 之间为自定义 **TCP JSON** 命令协议。

## 快速开始

```bash
git clone --recursive https://github.com/secosun/CADRender.git
```

1. **blenderserver**：见 `blenderserver/README.md`（`python -m uvicorn main:app --port 8060`）
2. **blenderworker**：`scripts/texture/sync_addon_to_blender.ps1`，Blender 侧栏启动 CADRender 控制服务
3. **renderui**：`cd renderui && npm install && npm run dev`（代理到 `:8060`）
4. **Worker**：在 `blenderworker` 目录，`PYTHONPATH=src`，`python -m worker_main`（配置 `BLENDERSERVER_URL`、`BLENDER_PORT`；见 [blenderworker/README.md](./blenderworker/README.md)）

## 子模块更新

```bash
git submodule update --remote --merge
```
