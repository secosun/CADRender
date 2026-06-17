# CADRender: AI-Driven 3D Product Rendering SaaS

参数化产品配置器的自动出图平台。用户选择产品模板 → 调整参数 → FreeCAD 生成 OBJ → Blender 渲染 → 下载成品图。

## 架构

```
renderui (React)
  → blenderserver (FastAPI)
      → freecad-worker (freecad-cli Docker)    # 参数化 OBJ 生成
      → blenderworker (Python TCP Client)       # Blender 渲染
          → Blender TCP :19876 (BlenderControlService)
```

| 模块 | 角色 |
|------|------|
| [blenderserver](./blenderserver) | SaaS 中台：JWT 认证、任务队列、模板管理、LLM 意图解析 |
| [blenderworker](./blenderworker) | Blender 执行内核：TCP 控制 + `core/` 电商渲染管线 |
| [freecad-worker](./blenderworker/src/freecad_worker) | 参数化 OBJ 生成：.FCStd 模板 + Spreadsheet 参数注入 |
| [renderui](./renderui) | Web 前端：模板选择、参数调节、任务管理 |

## 数据流

```
管理员上传 .FCStd 模板
       ↓
用户在 UI 选择模板、调整参数 (长度/宽度/厚度/孔径/表面处理)
       ↓
POST /api/tasks { template_id, template_params, scene_id }
       ↓ (异步)
freecad-worker → Docker freecadcmd → 打开 .FCStd → 设置 Spreadsheet 单元格 → recompute → 导出 OBJ
       ↓
blenderworker → Blender TCP → 导入 OBJ → 材质 → 灯光 → 渲染 → PNG
       ↓
用户查看/下载渲染结果
```

## 快速开始

1. **FreeCAD 验证**：`cd blenderworker && bash scripts/validate_freecad_docker.sh`
2. **blenderserver**：`cd blenderserver && python -m uvicorn main:app --port 8060`
3. **blenderworker**：`cd blenderworker && python -m src.worker_main`
4. **freecad-worker**：`cd blenderworker && python -m src.freecad_worker.main`
5. **renderui**：`cd renderui && npm install && npm run dev`（代理到 `:8060`）

## 生产部署

```bash
cd blenderserver
docker compose up -d                                          # 基础服务
docker compose --profile freecad up -d                        # 含 FreeCAD
docker compose --profile freecad -f docker-compose.yml up -d  # 完整部署
```
