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

### 前置条件

- Docker Desktop（启动全部容器服务）
- Blender 4.x（渲染引擎，安装在宿主机）
- Python 3.12+（可选，直接运行 blenderserver）
- Node.js 22+（可选，直接运行 renderui）

### 一键启动（Docker 推荐）

```powershell
# 1. 启动全部服务（redis + minio + blenderserver + renderui + blenderworker + freecad-worker）
docker compose -f docker-compose.dev.yml --profile full up -d

# 2. 启动宿主机 Blender TCP 渲染引擎
$env:BLENDER_ADDON_SRC = "D:\咸阳\框架评审\CADRender\blenderworker\src"
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" -b -P "D:\咸阳\框架评审\CADRender\blenderworker\blender_launcher_env.py"

# 3. 如果需要重启 worker（例如 Blender 重启后）
docker compose -f docker-compose.dev.yml restart blenderworker
```

### 分步启动（直接运行）

```bash
# 1. FreeCAD 验证
cd blenderworker && bash scripts/validate_freecad_docker.sh

# 2. 启动基础设施（redis + minio）
docker compose -f docker-compose.dev.yml --profile redis --profile s3 up -d

# 3. blenderserver
cd blenderserver && python -m uvicorn main:app --port 8060

# 4. blenderworker（需先启动宿主机 Blender TCP，见上方第 2 步）
cd blenderworker && python -m src.worker_main

# 5. freecad-worker
cd blenderworker && python -m src.freecad_worker.main

# 6. renderui
cd renderui && npm install && npm run dev
```

### 服务端口

| 服务 | 端口 | 地址 |
|------|------|------|
| renderui（前端） | 8050 | http://localhost:8050 |
| blenderserver（API） | 8060 | http://localhost:8060/docs |
| redis | 6379 | - |
| minio（S3） | 9000 / 9001 | http://localhost:9001 |
| Blender TCP（宿主机） | 19876 | 127.0.0.1 |

## 生产部署

```bash
cd blenderserver
docker compose up -d                                          # 基础服务
docker compose --profile freecad up -d                        # 含 FreeCAD
docker compose --profile freecad -f docker-compose.yml up -d  # 完整部署
```
