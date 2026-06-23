# 类目校准实操指南（CategoryCal + Human-in-the-loop）

> **定位**：在 **已标定材质** 基础上，为每个 **产品类目** 微调灯光位置、曝光、合成参数。
> 默认全链路 **Cycles + CV/CLIP**，VLM 可选；**不改** roughness/metallic 等材质旋钮。
>
> 代表模型与灯光几何 **绑定**——不做跨模型迁移验证；每类目需自己的代表 OBJ。
>
> CLI：`--scope category` 仅跑本模块；或 `--scope full` 在 finish 校准之后自动衔接（需 `--model`）。详见 [calibration_pipeline_design.md](./calibration_pipeline_design.md)。

---

## 快速路线图

```
材质 finish 已标定
    → 类目校准（代表 OBJ + category key）
    → [推荐] --no-auto-write → Admin UI 人眼选 Top-K
    → 写入 product_presets.json
    → scripts/render.py 生产出图
```

17 个产品类目均已配置 `gate_profile`（`dark_matte` / `mid_matte` / `mid_glossy` / `bright`），CV 门控阈值自适应。

---

## 架构概览

```
代表产品 OBJ + product_presets.json（材质/灯光 baseline）
       │
       ▼
Stage 0  几何预处理（bbox → 灯光距离/尺寸/能量）
       │
       ▼
Stage 1  灯光位置（Cycles + CV；可选 --use-vlm）
       │
       ▼
Stage 2  曝光 CV 引导（exposure_delta）
       │
       ▼
Stage 3  CLIP 合成（contrast_strength / glow_intensity）
       │
       ▼
[可选] Stage 4  VLM 精调（--use-vlm，灯光/曝光/合成 ±60%）
       │
       ▼
category_calibration_report.json（Top-5 候选 + 合并 params）
       │
       ▼
[人工] Admin UI 选最优 → product_presets.json
```

**VersionedState 合并规则**：每阶段存完整快照；复核报告中每个候选的 `params` 已按 Stage 1→N 累积合并，可直接写入 preset。

---

## 运行校准

**前提**：Blender TCP 已启动（默认 `127.0.0.1:19876`）。

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

# 推荐：只出报告，等人眼复核后再写 preset
python scripts/calibrate.py --mode category `
  --model assets/简易款-BodyPad003.obj `
  --category aluminum_6063 `
  --cal-quality standard `
  --no-auto-write

# 信任自动最优，直接写 preset
python scripts/calibrate.py --mode category `
  --model assets/guardrial.obj `
  --category aluminum_6063

# 特写相机（detail 模式，产出在 calibrate_out/detail/）
python scripts/calibrate.py --mode category `
  --model assets/guardrial.obj `
  --category aluminum_6063 `
  --detail `
  --no-auto-write

# 金标产品图（或类目 catalog_reference_image 自动加载）
python scripts/calibrate.py --mode category `
  --model assets/guardrial.obj `
  --category aluminum_6063 `
  --reference docs/assets/golden/reference_03_industry.png

# 启用 VLM Stage 1/4（需 CADRENDER_VLM_API_KEY）
python scripts/calibrate.py --mode category `
  --model assets/guardrial.obj `
  --category aluminum_6063 `
  --use-vlm
```

### CLI 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--model <obj>` | — | **必填**，该类目代表产品模型 |
| `--category <key>` | aluminum_6063 | product_presets 中的类目 key |
| `--no-auto-write` | off | 跳过写 preset，仅出复核报告 |
| `--use-vlm` | off | 启用 VLM 评分（Stage 1/4） |
| `--reference <png>` | — | 金标图；各阶段混合 reference_score |
| `--cal-quality` | standard | preview(256spp) / standard(512) / high(1024) |
| `--detail` | off | 特写相机，输出到 `calibrate_out/detail/` |
| `--skip-lighting` | off | 跳过 Stage 1 |
| `--skip-compositor` | off | 跳过 Stage 3 |
| `--dry-run` | off | 自动写入时只打印变更 |

---

## 产出文件

| 路径 | 内容 |
|------|------|
| `calibrate_out/fullshot/` 或 `detail/` | 按相机模式分目录 |
| `category_calibration_report.json` | **人眼复核主报告**（auto_best + Top-5 candidates） |
| `calibration_<run_id>.jsonl` | 全 trial 记录（recorder） |
| `stage1_*.png` / `calib_s2_*.png` / `calib_s3_*.png` | 各阶段 trial 渲染 |
| `product_presets.json` | 曝光 / 灯光 / 合成 / world / light_position_offsets |

### `category_calibration_report.json` 结构（摘要）

```json
{
  "category": "aluminum_6063",
  "camera_mode": "fullshot",
  "review_stage": 3,
  "auto_best": { "score": 7.2, "params": { "...": 0.1 }, "image": "calib_s3_007.png" },
  "candidates": [
    {
      "candidate_id": "s3_t007",
      "score": 7.2,
      "auto_rank": 1,
      "params": { "kx": 0.1, "exposure_delta": 0.15, "contrast_strength": 1.12, "...": "..." },
      "image": "calib_s3_007.png"
    }
  ],
  "human_pick": null
}
```

---

## 人眼复核（Admin UI）

需 **blenderserver** 挂载 `blenderworker/calibrate_out`（见 `docker-compose.dev.yml`）。

1. 打开 **Admin → 校准管理**（`/admin/calibration`）
2. 切换到 Tab **「类目校准」**
3. 选择类目 + `fullshot` / `detail`，加载报告
4. 并排对比 Top-K 候选图，点击放大
5. **「选为人眼最佳并写入 preset」** → 更新 `product_presets.json`，并在报告中记录 `human_pick`

### REST API（admin 写操作需登录）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/category-calibration-reports` | 列出已有报告 |
| GET | `/api/category-calibration-reports/{category}?camera_mode=fullshot` | 读取报告 |
| GET | `/api/category-calibration-reports/{category}/images/{filename}` | 候选 PNG |
| POST | `/api/category-calibration-reports/{category}/select-candidate` | 人眼选定并写 preset |

```json
// POST body
{ "candidate_id": "s3_t007", "camera_mode": "fullshot" }
```

---

## 写入 preset 的字段

| 来源 Stage | 写入 product_presets 的字段 |
|-----------|---------------------------|
| 1 | `light_position_offsets`（key/fill/rim xyz） |
| 2 | `render.preview.view_exposure`（累加 exposure_delta） |
| 3 | `render.preview.compositor`（contrast / glow / ao） |
| 4（--use-vlm） | `studio.*.energy_mult` / `size_mult` / `world.strength` 等 |

Baseline CV 指标写入 calibration overlay（非生产 preset 字段）。

---

## 与材质校准的关系

| | 材质校准 `--mode material` | 类目校准 `--mode category` |
|--|---------------------------|---------------------------|
| 频率 | 每种 finish 一次 | 每产品类目一次 |
| 优化对象 | roughness / metallic / specular / coat / bump | 灯光 / 曝光 / 合成 |
| 场景 | 标准球体 | 代表产品 OBJ |
| 验证 | 可选多模型 CV 迁移 | **不做**跨模型验证 |
| 人眼 UI | Tab「材质校准」 | Tab「类目校准」 |

推荐顺序：**先 material → 再 category → 再 render**。

---

## 生产渲染

```powershell
python scripts/render.py --model assets/guardrial.obj --category aluminum_6063
python scripts/render.py --model assets/guardrial.obj --category aluminum_6063 --full
```

---

## 复盘与调试

```python
from orchestration.calibration_recorder import review_calibration, print_review
print_review(review_calibration("calibrate_out/fullshot/calibration_20250618_120000.jsonl"))
```

```python
from orchestration.category_cal_review import merged_params_for_trial
# trials 来自 jsonl；merged_params_for_trial 复现 VersionedState 合并逻辑
```

---

## 注意事项

1. **历史跑法**（Eevee + 默认 VLM）与新管线不一致；需用当前 Cycles/CV 管线重跑才会生成 `category_calibration_report.json`。
2. **`--no-auto-write`** 适合首次标定或重大改版；日常迭代可省略，直接自动写 preset。
3. **`exposure_delta` 为相对值**：写入时累加 preset 现有 `view_exposure`；人眼选候选时 API 使用报告内已合并的 params。
4. 17 类目代表模型清单见 `docs/assets_todo.md`（待补全 OBJ 的类目需先准备代表模型再跑）。

---

## 相关文档

| 文档 | 内容 |
|------|------|
| `docs/material_calibration_guide.md` | 材质校准（MaterialCal v2） |
| `blenderworker/command.txt` | 命令速查 |
| `blenderworker/README.md` | Worker 总览 |
