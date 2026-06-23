# CADRender: AI-Driven 3D Product Rendering SaaS

参数化产品配置器的自动出图平台。管理员上传 .FCStd 模板 → 用户选择并调参 → FreeCAD 生成 OBJ → Blender 渲染 → 下载成品图。

## 架构

```
renderui (React + Three.js 3D 预览)
  → blenderserver (FastAPI)
      → freecad-worker (freecad-cli Docker)    # 参数化 OBJ 生成
      → blenderworker (Python TCP Client)       # Blender 渲染
          → Blender TCP :19876 (BlenderControlService)
```

| 模块 | 角色 |
|------|------|
| [blenderserver](./blenderserver) | SaaS 中台：JWT认证、任务队列、模板管理、LLM意图解析、支付宝/微信支付 |
| [blenderworker](./blenderworker) | Blender 执行内核：TCP控制 + 电商渲染管线 + 材质/类目校准 |
| [freecad-worker](./blenderworker/src/freecad_worker) | 参数化OBJ生成：.FCStd模板 + Spreadsheet参数注入 |
| [renderui](./renderui) | Web前端：模板选择、参数调节、Three.js 3D预览、颜色/finish/场景选择、任务管理、支付 |

## 颜色系统

| 模块 | 说明 |
|------|------|
| RAL K7 Classic 色库 | 217色，含中文名 + sRGB → Blender 线性转换 |
| ColorPicker 组件 | RAL 按系列分组展示，支持搜索和色块预览 |
| 模板颜色绑定 | Admin后台可多选绑定，未绑定时显示全部 |
| 任务传递 | `catalog_color` 经 intent_json → Blender 渲染管线 |

颜色数据文件：`blenderworker/blender_mcp_presets/catalog_colors.json`

## 表面处理系统

| 标准 | 数量 | 说明 |
|------|------|------|
| **蚁力系列（当前标准）** | **8** | 基于行业 Gold Standard 蚁力色卡 |
| 原有系列（废弃） | 14 | 标记 `deprecated: true`，待删除 |

Finish 配置：`blenderworker/blender_mcp_presets/finishes/*.json`
纹理配置：`blenderworker/blender_mcp_presets/texture_profiles/*.json`

## 场景系统

6 种预定义视觉场景，用户通过可视化 ScenePicker（渐变预览卡）选择：

| 场景 | 风格 | 适用 |
|------|------|------|
| `studio_neutral` | 标准影棚 | 通用 |
| `studio_high_key` | 高调亮白 | 浅色产品 |
| `studio_dark` | 暗调轮廓光 | 深色/金属 |
| `studio_soft` | 大面积柔光 | 曲面/反光 |
| `outdoor_overcast` | 阴天漫射 | 自然光效果 |
| `outdoor_sunset` | 日落暖光 | 暖色氛围 |

场景定义：`blenderworker/src/core/scene_engine.py`

## 外观校准（Look-dev）

统一入口 `scripts/calibrate.py --scope`，子模块：材质球 PBR → 参考图纹理 → 产品类目。

```
材质校准（球体）→ 纹理校准（蚁力参考图）→ 类目校准（产品模型）→ render.py 出图
```

| 步骤 | 命令 | 文档 |
|------|------|------|
| 统一管线 | `calibrate.py --scope finish` | [calibration_pipeline_design.md](./docs/calibration_pipeline_design.md) |
| 材质校准 | `calibrate.py --scope material` | [material_calibration_guide.md](./docs/material_calibration_guide.md) |
| 纹理校准 | `calibrate.py --scope texture` | [texture_calibration_design.md](./docs/texture_calibration_design.md) |
| 类目校准 | `calibrate.py --scope category` | [category_calibration_guide.md](./docs/category_calibration_guide.md) |

## 设计文档

- [统一校准管线](./docs/calibration_pipeline_design.md) — 单入口、三子模块、scope 与场景分工
- [纹理校准设计思想](./docs/texture_calibration_design.md) — 参考图驱动、生产 bakecoat、对称评分
- [材质校准指南](./docs/material_calibration_guide.md) — PBR 参数校准流程
- [类目校准指南](./docs/category_calibration_guide.md) — 曝光/灯光/合成/VLM 校准

### 前置条件

- Docker Desktop（启动全部容器服务）
- Blender 4.x（渲染引擎，安装在宿主机）
- 环境要求：**必须使用 Docker 运行服务端**，禁止本地直接启动 blenderserver

### Docker 启动（推荐）

```powershell
# 1. 启动全部服务（Redis + blenderserver + renderui）
docker compose -f docker-compose.dev.yml --profile redis --profile server --profile ui up -d --build

# 2. 启动宿主机 Blender TCP 渲染引擎
$env:BLENDER_ADDON_SRC = "D:\咸阳\框架评审\CADRender\blenderworker\src"
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" -b -P "D:\咸阳\框架评审\CADRender\blenderworker\blender_launcher_env.py"
```

### 服务端口

| 服务 | 端口 | 地址 |
|------|------|------|
| renderui（前端） | 8050 | http://localhost:8050 |
| blenderserver（API） | 8060 | http://localhost:8060/docs |
| redis | 6379 | - |
| minio（S3） | 9000 / 9001 | http://localhost:9001 |
| Blender TCP（宿主机） | 19876 | 127.0.0.1 |

### API 端点

| 端点 | 说明 |
|------|------|
| `GET /api/colors` | RAL 217色 + 系列分组 |
| `GET /api/finishes` | 全部 surface finish |
| `GET /api/texture-profiles` | 全部纹理配置 |
| `GET /api/scenes` | 场景列表 |
| `GET /api/freecad/templates` | 模板列表 |

## 数据流

```
管理员上传 .FCStd 模板 (预制模型，非用户上传)
       ↓
用户在 UI 选择模板、调整参数、选颜色/finish/场景
       ↓
Three.js 实时 3D 预览 (内置 OBJ，非用户上传)
       ↓
POST /api/tasks { template_id, template_params, scene_id, catalog_color, surface_finish }
       ↓ (异步)
freecad-worker → Docker freecadcmd → 打开 .FCStd → 设置 Spreadsheet → recompute → 导出 OBJ
       ↓
blenderworker → Blender TCP → 导入 OBJ → 材质 → 灯光 → 渲染 → PNG
       ↓
用户查看/下载渲染结果
```

## 产品流程

### 外观校准（Look-dev）

两步一次性标定，之后无限次生产渲染：

```
材质校准（每 finish）→ 类目校准（每 category）→ scripts/render.py 出图
```

| 步骤 | 命令 | 文档 |
|------|------|------|
| 材质校准 | `calibrate.py --mode material` | [material_calibration_guide.md](./docs/material_calibration_guide.md) |
| 纹理校准 | `calibrate.py --mode texture` | [texture_calibration_design.md](./docs/texture_calibration_design.md) |
| 类目校准 | `calibrate.py --mode category` | [category_calibration_guide.md](./docs/category_calibration_guide.md) |

## 环境配置

新环境先读 [environment_config.md](./docs/environment_config.md)，其中 `cadrender-env` 块可被脚本自动解析：

```powershell
.\scripts\load_calibration_env.ps1          # 加载到当前 PowerShell 会话
python scripts\load_calibration_env.py --write .env   # 生成 .env 模板
```

`blenderworker/scripts/calibrate.py` 启动时会自动加载同一配置（文档块 + `.env`，不覆盖已 export 的变量）。

## 设计文档

- [环境配置](./docs/environment_config.md) — VLM、Blender TCP、校准相关环境变量
- [纹理校准设计思想](./docs/texture_calibration_design.md) — 纹理/颜色解耦、两阶段校准、配置分层
- [材质校准指南](./docs/material_calibration_guide.md) — PBR 参数校准流程
- [类目校准指南](./docs/category_calibration_guide.md) — 曝光/灯光/合成/VLM 校准
