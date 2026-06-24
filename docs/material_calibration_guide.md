# 材质标定实操指南（MaterialCal v2）

> **定位**：本系统校准的是 **渲染外观 preset**（look-dev），使 catalog 出图风格稳定一致；
> 输出的 `roughness` 等数值是 **Blender Principled 旋钮**，不是实验室测得的 BRDF 参数。
>
> `calibrate.py --scope material` / MaterialModule：**仅材质球 PBR**（roughness / metallic / specular / coat / 基材各向异性）。
> **纹理不由球体校准**——有 `texture_profile` 的 finish 由 **TextureModule**（平板 + 蚁力参考图）独立负责；推荐 `--scope finish` 一次跑完两阶段。
>
> 生产对齐球体 + 256→1024spp 确认 + Optuna + 可选多模型验证 + 条件写入 finish JSON。

---

## 快速路线图

```
已有 11 种 finish → 直接用，零配置
新材质 → 创 finishes JSON → 跑校准（建议带 --model 验证）
       → 类目校准（--no-auto-write + UI 人眼选 Top-K）→ 生产渲染
```

已有材质：`powder_matte` / `powder_glossy` / `anodized_black` / `anodized_silver` /
`brushed_aluminum` / `stainless_brushed` / `champagne_gold` / `electrophoretic` /
`fluorocarbon` / `gray_silver_metallic` / `wood_transfer` / **`outdoor_sand`（铝基材+砂纹漆）**

---

## 架构概览

**铝型材 + 喷涂漆面**（`substrate_finish_id`）：

```
finishes/outdoor_sand.json
  substrate_finish_id → brushed_aluminum_voronoi（拉丝铝 · 球体定 PBR）
  texture_profile     → outdoor_sand（砂纹漆 · 平板+参考图定纹理）
       │
       ▼
finish_resolve.py（merge_substrate_finish）
  principled: metallic/anisotropic ← 基材；base_color/coat_* ← 漆面
  bakecoat: substrate_brush（Voronoi）+ M_Bakecoat 砂纹
       │
       ▼
calibrate.py --scope finish
  MaterialModule（球）→ 漆层 PBR + 基材各向异性
  TextureModule（板）→ bakecoat 砂纹 vs 蚁力参考
       │
       ▼
build_bakecoat_principled（生产：Voronoi 拉丝 + M_Bakecoat 同栈）
```

无 `substrate_finish_id` 的 finish 仍走原单材质球路径（plain Principled + 可选 bakecoat）。

```
finishes/<id>.json
       │
       ▼
finish_cal_spec ──► 球体场景 = 生产 Shot_Key/Fill/Rim + HDRI + view_exposure
       │
       ▼
bakecoat 生产材质栈 + Optuna @ 256spp（R/M/S + coat + bump_mult）
       │
       ▼
top-3 复验 @ 1024spp（降低噪声最优）
       │
       ▼
加权 sigmoid 评分（或 --reference 金标 SSIM）+ calibration_report.json
       │
       ▼
[可选] 多产品模型 before/after CV 验证（worst-case）
       │
       ▼
写入 finishes/<id>.json（验证 FAIL 时默认拒绝）
```

---

## 第一步：创建材质 JSON

新建 `blender_mcp_presets/finishes/<your_finish>.json`：

```json
{
  "id": "my_new_finish",
  "label_zh": "我的新材质",
  "gate_profile": "mid_matte",
  "lighting_profile": "mid",
  "material_folder": "materials/finishes/my_new_finish",
  "view_exposure": -0.4,
  "hdri_strength": 0.4,
  "world_strength": 0.2,
  "calibration": {
    "lock_metallic": true,
    "substrate_finish_id": "brushed_aluminum_voronoi"
  },
  "principled": {
    "base_color": [0.52, 0.55, 0.60, 1.0],
    "coat_weight": 0.55,
    "coat_roughness": 0.28
  },
  "bakecoat_procedural": {
    "bump": { "strength": 0.02, "distance": 1.0 },
    "micro": { "scale": 720, "detail": 11, "roughness": 0.48 },
    "rough_mix_factor": 0.7
  }
}
```

带 `substrate_finish_id` 的 finish（如 `outdoor_sand`）在加载时自动合并拉丝铝基材；材质球阶段搜漆层 PBR，平板阶段搜砂纹纹理。

**`base_color` 是唯一必须人工精确定义的参数**；`lighting_profile` 决定球体与生产使用同一套灯光。

| 材质类型 | gate_profile | lighting_profile |
|---------|-------------|-----------------|
| 深色哑光（黑/深灰喷粉） | `dark_matte` | `dark` |
| 中等色调（银灰/香槟/拉丝铝） | `mid_matte` | `mid` |
| 亮色（白/浅灰） | `bright` | `light` |
| 高反光金属 | `mid_matte` | `bright` |

---

## 第二步：运行校准

确保 **Blender TCP 已启动**（`:19876`）。

```powershell
cd blenderworker
$env:PYTHONPATH = "src"
```

### 统一入口：`--scope` 选环节

与 [calibration_pipeline_design.md](./calibration_pipeline_design.md) 一致——可 **一次性串联**，也可 **单独跑某一环**：

| 目标 | 命令 |
|------|------|
| 材质 + 纹理（推荐） | `--scope finish --finish-id <id> --reference <蚁力crop>` |
| 材质 + 纹理 + 类目 | `--scope full` + 上列 + `--model <obj>` |
| 仅材质球 PBR | `--scope material --finish-id <id>` |
| 仅纹理平板 | `--scope texture --finish-id <id> --reference <蚁力crop>` |
| 仅类目 | `--scope category --model <obj> --category <key>` |

旧写法 `--mode material|texture|category` 仍可用，分别对应上表三个单环节；**不含** `finish` / `full`。

### 仅材质球（`--scope material`）

```powershell
# 推荐：球体 Optuna + 多模型 worst-case 验证
python scripts/calibrate.py --scope material `
  --finish-id my_new_finish `
  --models assets/guardrial.obj,assets/简易款-BodyPad003.obj `
  --category aluminum_6063

# 单模型验证
python scripts/calibrate.py --scope material `
  --finish-id my_new_finish `
  --model assets/guardrial.obj `
  --category aluminum_6063

# 仅球体（更快，无迁移验证）
python scripts/calibrate.py --scope material --finish-id my_new_finish

# 快速迭代（跳过 1024spp 确认）
python scripts/calibrate.py --scope material --finish-id my_new_finish --skip-confirm

# 金标球图（SSIM+直方图，覆盖 heuristic 评分）
python scripts/calibrate.py --scope material --finish-id my_new_finish `
  --reference docs/assets/golden/sphere_powder_matte.png
```

> **注意**：有 `texture_profile` 的 finish（如 `outdoor_sand`）**不要在球体阶段期望纹理收敛**；纹理由 TextureModule 负责，请用 `--scope finish` 或 `--scope texture`。

### 材质 + 纹理（`--scope finish`，如 outdoor_sand）

```powershell
# 审查模式：不写 preset
python scripts/calibrate.py `
  --scope finish `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --no-auto-write

# 确认后落盘
python scripts/calibrate.py `
  --scope finish `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png

# 仅重导纹理审查图（已有 best_params）
python scripts/render_texture_review.py --finish-id outdoor_sand
```

Ball：铝基材 + 漆层 PBR；Plane：对照蚁力参考搜砂纹。详见 [texture_calibration_design.md](./texture_calibration_design.md)。

### Live Review（校准中实时看图）

校准跑 Optuna 时，加 `--live-review` 会从控制台进程**直接弹出桌面窗口**，布局为 **2×2 双栏对比**：

| | 左栏 | 右栏 |
|---|------|------|
| **上行** | 上一张 trial | 当前 trial |
| **列内** | Beauty PBR \| Proxy 伪彩 | Beauty PBR \| Proxy 伪彩 |

底部显示当前轮次与 Optuna 参数；纹理 stage 每 trial 先渲染 beauty 再渲染 proxy（`pass_kind=texture_dual`）。**Optuna 主评分仍用 Proxy**，Beauty 仅用于人眼/VLM 审查（含暗场曝光、bump 放大等审查专用后处理，不影响 proxy 分数）。

```powershell
# 每帧自动刷新窗口
python scripts/calibrate.py --scope finish `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --live-review

# 人工 gate：每帧点 Continue 才继续下一轮 trial
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --live-review --live-review-wait

# VLM 自主闭环 + Live Review
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --texture-trials 12 `
  --texture-vlm-loop `
  --texture-vlm-max-rounds 3 `
  --live-review
```

| 参数 | 说明 |
|------|------|
| `--live-review` | 弹出 tkinter 桌面窗口（Beauty \| Proxy 双栏） |
| `--live-review-wait` | 阻塞直到窗口点 Continue |
| `--live-review-no-beauty-trials` | 纹理 trial 不额外 beauty（仅 export 时 `beauty_best`） |
| `--texture-vlm-loop` | 多轮 Optuna → VLM 评价 → 自动调 bounds；产物 `texture_vlm_loop.json` |
| `--texture-vlm-max-rounds` | VLM 闭环最大轮数（默认 3） |
| `--texture-vlm-pass-score` | VLM overall_score 达标阈值（默认 0.72） |

产物：`calibrate_out/live_review/current.png`（最新帧副本）。事后复核仍用 Admin `/admin/calibration`。

### 定稿验收（preset 写入后）

材质 + 纹理 preset 定稿后，用生产全栈路径验收（**勿**用 `--calibration` 模式的 `preview.py`，该模式会剥掉漆面砂纹）：

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

# 金属球 + 平板 compare_triple
python scripts/acceptance_finish.py --finish-id outdoor_sand

# 从 VLM 各轮中选 feature 最高一轮写入 preset（可与 pipeline 最终选中 trial 不同）
python scripts/write_feature_best_round.py outdoor_sand

# 仅金属球预览（生产 resolve_finish_cfg）
python scripts/preview.py --finish outdoor_sand --texture outdoor_sand --samples 256
```

| 产物 | 路径 |
|------|------|
| 金属球验收 | `calibrate_out/acceptance_<id>/shader_ball.png` |
| 平板三栏 | `calibrate_out/texture_<id>/compare_triple.png` |

### 全流程（`--scope full`）

```powershell
python scripts/calibrate.py `
  --scope full `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --model assets/guardrial.obj `
  --category aluminum_6063 `
  --no-auto-write
```

材质/纹理 PASS 后进入 CategoryModule；类目细节见 [category_calibration_guide.md](./category_calibration_guide.md)。

### 校准过程（约 10–25 分钟，视 trial 数、确认阶段与验证模型数）

| 步骤 | 内容 |
|------|------|
| 1 | 倒角球体 + **finish 对应 lighting_profile** + HDRI + AgX |
| 2 | 应用生产 **bakecoat** 材质栈 |
| 3 | Optuna **32 trials @ 256spp**：roughness / metallic / specular；有 coat/bakecoat 时额外搜 coat 与 bump_mult |
| 4 | **top-3 @ 1024spp** 复验，从确认分数选最终参数 |
| 5 | 加权 sigmoid 评分（阴影区 albedo + CIEDE2000） |
| 6 | [可选] 多产品模型 baseline vs candidate **worst-case CV** |
| 7 | 输出 `calibration_report.json` + `00_summary_grid.png`；验证 PASS 后写入 JSON |

### CLI 参数

| 参数 | 说明 |
|------|------|
| `--scope finish\|full\|material\|texture\|category` | 选择校准环节（见上表） |
| `--no-auto-write` | 只出审查产物，不写 preset |
| `--material-trials N` | Optuna 轮数（默认 32） |
| `--search-samples N` | 搜索阶段 Cycles spp（默认 256） |
| `--confirm-samples N` | 确认阶段 spp（默认 1024） |
| `--confirm-top-k N` | 复验 top-K trial（默认 3） |
| `--skip-confirm` | 跳过确认阶段 |
| `--model <obj>` | 单产品 → 触发 `validation/` |
| `--models a.obj,b.obj` | 多产品 worst-case 验证 |
| `--category <name>` | 验证时 product category（默认 aluminum_6063） |
| `--reference <png>` | 金标球图，用 SSIM+hist+edge 替代 heuristic |
| `--force-write` | 验证失败仍写入 JSON |
| `--dry-run` | 只打印变更 |

### 你需要做的

1. 打开 `calibrate_out/material_<finish_id>/00_summary_grid.png` 目视确认
2. 查看 `calibration_report.json` 的 `trial_stats`（mean/std）评估搜索稳定性
3. 若带了 `--model`/`--models`，查看 `validation/validation_summary.json` 的 `worst_cv_delta`
4. 验证 PASS → JSON 已自动更新；FAIL → 调 finish 起点或加 `--reference`，勿用 `--force-write` 除非人工确认
5. **可选**：Admin `/admin/calibration` → Tab「材质校准」→ 从 trial 图集中另选更优参数写入 finish JSON

### 人工 spot-check（与自动 gate 并列）

| 检查项 | 通过标准 |
|--------|---------|
| 底色 | 阴影区不发灰、不发绿（对照实物或金标） |
| 高光 | 形状自然、无大面积 clip |
| 颗粒/微对比 | 哑光有适度纹理，非塑料感 |

### 离线 regression

校准完成后对照 manifest 阈值（无需 Blender）：

```powershell
python scripts/material_regression_check.py --output-dir ./calibrate_out
```

阈值配置：`blender_mcp_presets/calibration_regression.json`

### 搜索范围

| 参数 | 范围 | 条件 |
|------|------|------|
| roughness | 0.10 – 0.85 | 始终 |
| metallic | 0.00 – 1.00 | 始终 |
| specular | 0.00 – 1.00 | 始终 |
| coat_weight / coat_roughness | ±0.12 | principled.coat_weight > 0.01 |
| bump_mult | 0.75 – 1.35 | 存在 bakecoat_procedural |

---

## 评分说明

**默认（方案 A）**：四维加权 sigmoid，权重和 = 1，色彩约 30%。

```
score = 10 × (w₁·σ(lum_std) + w₂·σ(p95) + w₃·σ(grad) + w₄·CIEDE2000_shadow)
```

- 色彩对比：**阴影区像素**（12–28% 亮度带）估计 albedo，与 `base_color` Lab 比 CIEDE2000
- 权重按 `gate_profile` 预设；`metallic ≥ 0.5` 时加重高光维

**可选（方案 B）**：`--reference` 金标球图 → `reference_score`（SSIM×0.4 + hist×0.4 + edge×0.2）

---

## 第三步：类目校准与生产

材质校准完成后，对该产品类目跑一次类目校准（不改材质）。

**推荐**：先 `--no-auto-write` 出报告，在 Admin UI 人眼选 Top-K 后再写 preset。

```powershell
# 推荐流程：自动搜参 → UI 人眼复核 → 写 preset
python scripts/calibrate.py --mode category `
  --model assets/简易款-BodyPad003.obj `
  --category aluminum_6063 `
  --cal-quality standard `
  --no-auto-write

# 或直接自动写入（跳过 UI）
python scripts/calibrate.py --mode category `
  --model assets/guardrial.obj `
  --category aluminum_6063
```

### 类目校准要点

| 项目 | 说明 |
|------|------|
| 引擎 | 默认全链路 **Cycles**（Stage 1–3）；`--use-vlm` 可选 Stage 4 |
| 评分 | CV（Stage 1/2）+ CLIP（Stage 3）；VLM 默认关闭 |
| 金标 | `--reference` 或类目 `catalog_reference_image` 自动加载 |
| 验证 | **不做**跨模型迁移；代表 OBJ 与灯光绑定 |
| gate_profile | 17 类目已配置，CV 阈值自适应 |

### 产出与复核

| 路径 | 用途 |
|------|------|
| `calibrate_out/fullshot/category_calibration_report.json` | Top-5 候选 + 合并 params |
| `calibrate_out/fullshot/calib_s3_*.png` 等 | 候选渲染图 |
| `product_presets.json` | 自动写入或 UI 选定后写入 |

**Admin UI**：`/admin/calibration` → Tab **「类目校准」** → 对比候选 → 「选为人眼最佳并写入 preset」

**材质 UI**（同页 Tab「材质校准」）：对比 trial 球体 → `select-trial` 写 finish JSON

详细说明见 **`docs/category_calibration_guide.md`**。

然后生产渲染：

```powershell
python scripts/render.py --model assets/guardrial.obj --category aluminum_6063
```

---

## 材质参数速查

| 参数 | 范围 | 说明 |
|------|------|------|
| roughness | 0–1 | 越低越亮、高光越锐 |
| metallic | 0–1 | 喷粉 0，金属 ~1 |
| specular_ior_level | 0–1 | 非金属高光强度 |
| coat_weight | 0–1 | 清漆层 |
| coat_roughness | 0–1 | 清漆粗糙度 |
| bakecoat.bump.strength | — | 颗粒感；bump_mult 相对缩放 |

常见起点见下表，校准会覆盖 principled 与 bump.strength：

| 材质 | roughness | metallic | specular | coat_weight |
|------|-----------|----------|----------|-------------|
| 哑光黑喷粉 | ~0.50 | 0.0 | ~0.3 | ~0.20 |
| 拉丝铝（Voronoi） | ~0.32 | 1.0 | ~0.39 | 0.0 |
| 阳极氧化黑 | ~0.30 | 1.0 | ~0.5 | ~0.15 |

> **拉丝铝** 生产默认已切换为 **Voronoi 程序化**（`brush_mode: voronoi`）。Wave 备用：`brushed_aluminum_wave`。

---

## 拉丝铝专项（Voronoi 高光切割器）

### 设计原则

拉丝铝的本质是 **微表面各向异性**，不是表面沟槽纹理。

| 判断标准 | 说明 |
|---------|------|
| ✅ 正确 | 关掉主光、仅环境光时 **看不到条纹**；条纹只在 **高光带** 里呈细丝 |
| ❌ 错误（砂纸感） | 亮到暗全表面有竖纹 → Voronoi 在驱动 Bump/Base Color |

### 节点拓扑（`M_VoronoiBrush`）

```
Voronoi (F1, Distance to Edge, randomness≈0.1)
    │
    ├─ MapRange 反转（边缘距离小 → 高 fac）
    ├─ ColorRamp [0.0=black, 0.02=white]  CONSTANT，极窄边界
    │       └─→ Anisotropic += strength×0.15（仅切割高光）
    │
    └─ connect_bump=false（默认不连 Normal；可选极弱 0.03）
```

关键 preset 字段：

| 参数 | 生产默认 | 说明 |
|------|---------|------|
| `mapping.scale` | `[1600, 1, 0]` | X 拉伸细纹；Z=0 减轻球体极点压缩 |
| `ramp_white_pos` | `0.02` | 只保留发丝级边界 |
| `voronoi_randomness` | `0.1` | 避免豹纹细胞 |
| `anisotropic_voronoi_strength` | `0.15` | 只调制各向异性 |
| `connect_bump` | `false` | 不铺全表面凹凸 |
| `bump_noise_strength` | `0` | 去掉边缘颗粒 |

高光切割器修正后需配合 **scorer v3**（中调 |Gx| 微沟槽 + 镜面惩罚）重跑校准；旧版会把镜面球打到 ~8.2。

### 校准命令

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

python scripts/calibrate.py --mode material `
  --finish-id brushed_aluminum `
  --search-samples 512 --confirm-samples 1024 --no-auto-write

python scripts/test/brushed_aluminum_ab_review.py
```

同步节点组到 Blender 后需 **禁用再启用 MCP 插件** 或重启 Blender。

### A/B 与 Admin

| 标签 | 方案 | Admin |
|------|------|-------|
| A | Wave 校准 | — |
| **B** | **Voronoi 校准** | **✅ 最佳（方向对，待高光切割器修正）** |
| C | Voronoi+Wave | — |

### 相关 finish

| ID | 用途 |
|----|------|
| `brushed_aluminum` | 生产默认（Voronoi 高光切割器） |
| `brushed_aluminum_wave` | Wave 拉光备用 |
| `brushed_aluminum_voronoi` | 同参别名 |

---

## 配色扩展

在 `blender_mcp_presets/catalog_colors.json` 中为 finish 增加配色（仅覆盖 `base_color`）。

---

## 从简单开始

1. 先用 `powder_matte` + 已有配色
2. 新 finish：**务必设对 `lighting_profile`**，与产品类目一致
3. 校准命令**尽量带 `--model`**，让系统自动做迁移验证
4. 验证 FAIL 时先看 `validation_report.json`，再决定是否 `--force-write`
