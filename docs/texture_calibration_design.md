# 纹理校准设计思想

> **2026-07 修订**：新增纹理贴图提取管线（`extract_texture_map.py` + `--use-texture-map`），从蚁力色卡提取干净贴图作为程序化拟合的评分目标，提升评分信噪比。  
> **2026-06 修订**：paint-only 校准栈、direction isotropy 评分（20%）、Coat Normal 接线修复、Live Review 先 proxy 后 beauty、`run_texture_cal_round.py` 归档对比。  
> **业务公式**：`模型 × finish × texture × category → HD 成片` — 见 [texture_calibration_roadmap.md §1](./texture_calibration_roadmap.md)。  
> **推进策略**：先 outdoor_sand 四维组合定稿，再按 [roadmap](./texture_calibration_roadmap.md) 扩展。

## 背景

产品均为 **铝型材 + 喷涂漆面**。Finish 名称（如 `outdoor_sand`）表示 **漆面纹理/外观**，不是另一种基材。

表面处理由独立维度组成：

- **铝基材**：拉丝/各向异性 — `substrate_finish_id`（默认 `brushed_aluminum_voronoi`）→ **材质球** 定 PBR
- **颜色**：RAL 色库 + 漆面 `base_color`
- **漆层 PBR**：`coat_weight` / `coat_roughness` 等 — **材质球** 子模块
- **漆面纹理**：`bakecoat_procedural`（砂纹 noise / rough_mix）— **参考图 + 平板** 子模块

纹理描述「漆面颗粒质感」，与颜色无关；必须与蚁力色卡实物对比。

## 铝基材 + 漆面（substrate_finish_id）

`finishes/outdoor_sand.json` 示例：

```json
{
  "id": "outdoor_sand",
  "substrate_finish_id": "brushed_aluminum_voronoi",
  "principled": { "base_color": [...], "coat_weight": 0.59, ... },
  "bakecoat_procedural": { "micro": {...}, "rough_mix_factor": 0.7 },
  "texture_profile": "outdoor_sand"
}
```

合并逻辑（`orchestration/calibration/shared/finish_resolve.py`）：

| 来源 | 写入合并 finish |
|------|----------------|
| 基材 `brushed_aluminum_voronoi` | `metallic=1`、各向异性、`substrate_brush`（Voronoi 拉丝） |
| 漆面 finish | 漆色、`coat_*`、M_Bakecoat 砂纹参数 |

生产材质节点：**Voronoi 拉丝（Anisotropic）→ 主 BSDF Normal；M_Bakecoat 砂纹 → Coat Normal + Coat Roughness** 同栈叠加。

### Principled 主 BSDF vs Coat（物理分层）

Blender 4.x Principled 中，主 BSDF 与 Coat 是**分层光传输**，不是参数简单叠加：

| 层 | 物理角色 | 我们的参数 |
|----|----------|------------|
| **主 BSDF** | 铝型材本体（Metallic、Base Color、低 Roughness、拉丝 Normal） | `substrate_finish_id` + `roughness≈0.25` |
| **Coat** | 喷涂漆膜（IOR、Coat Roughness、Coat Normal、Coat Tint） | `coat_weight≈1.0` + M_Bakecoat 程序化 |

接线规则（`core/bakecoat_targets.py` + `material_builders.py`）：

- `connect_roughness_to_coat: true` → M_Bakecoat **Roughness → Coat Roughness**（橘皮/哑光）
- M_Bakecoat **Normal → Coat Normal**（漆膜微观起伏；按 `coat_normal_strength` 放大）
- **实现注意**：Blender 4.x 节点组 `node.type == "GROUP"`（非旧版 `ShaderNodeGroup`）；`_apply_anisotropy_and_coat` 与 `_attach_m_bakecoat_group` 必须在 `paint_on_coat` 时接线，否则全漆层下砂纹不可见。
- **禁止**砂纹 roughness 同时接主 BSDF（喷漆后铝底不可见，主 Roughness 仅保暗部金属反射）
- 材质球校准：`lock_substrate_roughness` 锁定铝底 Roughness，只搜 `coat_weight` / `coat_roughness`
- 验收/预览：`purpose=acceptance` 使用亮场灯光，与校准暗场分离

## 在统一管线中的位置

纹理校准是 `calibrate.py --scope finish` 的 **第二阶段**（材质球 PBR 之后）：

```
MaterialModule（球体 · 铝基材+漆层 PBR）→ TextureModule（平板 · 蚁力参考 · 漆面砂纹）→ [CategoryModule]
```

实现代码：

| 层 | 路径 |
|----|------|
| 子模块 | `orchestration/calibration/texture_module.py` |
| 引擎 | `orchestration/calibration/texture_engine.py` |
| 节点构建 | `core/material_builders.py`（Coat Normal、`GROUP` 类型） |
| 归档重跑 | `scripts/run_texture_cal_round.py` |
| VLM 闭环 | `orchestration/calibration/shared/texture_vlm_loop.py` |
| Live Review | `orchestration/calibration/shared/live_review.py` |
| 场景常量 | `orchestration/calibration/shared/scene_texture_panel.py` |
| 对称评分 | `orchestration/calibration/shared/scoring_reference.py` |

总览见 [calibration_pipeline_design.md](./calibration_pipeline_design.md)。

## 设计原则

### 1. 纹理独立于颜色

- 纹理配置：`texture_profiles/*.json`
- Finish 通过 `texture_profile` 引用
- 校准渲染时 `base_color` 固定中灰 `(0.45, 0.45, 0.45)`，评分不看颜色

### 2. 参考图驱动（Ground Truth = 蚁力色卡）

- **必须**提供 `--reference`（如 `outputs/yili_crops/outdoor_sand_crop.png`）
- 裁剪脚本：`scripts/crop_yili_references.py`
- 无参考图时 TextureModule **拒绝启动**（不用启发式代替人眼标准）

### 3. 生产材质对齐

校准与生产使用同一栈：

```
build_bakecoat_principled() → M_Bakecoat（micro / fine / hyperfine bump 叠层 + rough_ramp + rough_mix）
```

禁止在校准中使用简化 Noise+单 Bump 节点树（否则搜到的参数无法迁移到生产）。

### 4. 纹理平板场景

**Proxy 评分 pass**（Optuna 主依据）：

| 要素 | 说明 |
|------|------|
| 几何 | `CalPanel` 平面（约 0.3×0.4 m） |
| 材质 | **paint-only**：仅 M_Bakecoat 砂纹漆层，**不含** `substrate_brush` / Voronoi 拉丝 |
| 坐标 | `mapping.coord = OBJECT`，`scale = [1,1,1]`（严禁拉伸，避免伪斜纹） |
| principled | 中性灰、`coat_weight=0`（proxy 只看 roughness emission，与生产 coat 栈解耦） |
| 相机 | 正交或低仰角，与特征 pass 一致 |

**Beauty 审查 pass**（人眼 / Live Review / `beauty_best.png`）：

| 要素 | 说明 |
|------|------|
| 材质 | **paint-only** + 完整 **coat 栈**（`coat_weight=1`、`connect_roughness_to_coat`）；`anisotropic=0` |
| 相机 | 微距透视（~110–125 mm），面板倾角 ~28°（弱梯度，减少假斜纹） |
| 灯光 | 较大面积 Key + 较强 Fill（约 0.52 / 0.38 W），弱世界光 |
| 分辨率 | trial 内 **512² / 96 spp**；export `beauty_best` **768² / 192 spp** |
| bump / rough_mix | **与 proxy 相同**（`_flat_params_to_bakecoat`，无 ×1.12 等审查 fudge） |
| principled | coat 栈 + `anisotropic=0`（仅 PBR 层，不改 bakecoat 数值） |

材质球场景 **不用于** 纹理校准。铝基材拉丝仅在 **生产渲染 / `acceptance_finish.py` 金属球** 中可见。

### 4.1 模块独立与定稿参数（Proxy 为唯一真源）

TextureModule 与 Material / Category **解耦**。纹理维交付物：

| 交付物 | 含义 | 是否写入 preset |
|--------|------|----------------|
| **`best_params`** | proxy Optuna 最优 trial 的 8 参 | ✅ `texture_profiles` + `finishes.bakecoat_procedural` |
| **`proxy_best.png`** | 上述参数在平板场景的 **可视化**（伪彩审查） | 审查图 |
| **`proxy_texture.png`** | 同上参数的 roughness 细节 pass | 审查 / VLM 闭环输入 |
| **`beauty_best.png`** | 同 **proxy 参数** + Beauty 审查栈（coat PBR，仅光照/相机不同） | 人眼审查 |
| **`vlm_rerank_params`** | Beauty VLM 在 top-3 上的建议（可选） | ❌  advisory |

**原则**：

1. 平板 proxy 可视化图对应的参数 **就是** 定稿参数；不存在「proxy 最优 trial A、写入 preset 却是 trial B」。  
2. Beauty 与 proxy **bakecoat 参数完全一致**；差异仅在渲染 pass（伪彩 vs coat PBR + 微距光）。  
3. Beauty 与 proxy **指标不混用**：Optuna / `best_score` / 写盘均来自 proxy Feature。  
4. **可复用**的是 `best_params`（或贴图 asset），由 `texture_profile` 挂到任意模型。  
5. 生产全栈在 `render.py` / `acceptance_finish` 上 **组合验收**。

### 5. 对称特征评分 + 可选 VLM

**问题 A（评分域）**：若只对参考图做高通、渲染 beauty pass 不做，Optuna 在比「光照」而非「纹理」。

**问题 B（beauty pass 平坦）**：高 `rough_mix` 哑光 finish 的 beauty 图在平板上几乎均匀灰度，Optuna 无信号。

**做法**：

1. 参考图与 trial 图 **同一套** `preprocess_reference` 后再提取特征。
2. **Optuna 主评分使用 roughness 代理 pass**（M_Bakecoat `rough_mix` + `rough_ramp` → Emission），与生产参数对齐、与光照解耦。
3. **paint-only 栈**：校准/评分/Beauty 审查均剥离 `substrate_brush`，避免 Voronoi 拉丝污染「各向同性砂纹」搜索。
4. **方向性惩罚**：梯度方向熵（isotropy）占 feature 分 **20%**，抑制「斜拉丝/拉伸 noise」高分解。
5. 写入生产仍走完整 `resolve_finish_cfg`（铝基材 + coat + M_Bakecoat）。
6. **Beauty 与 Proxy 分离**：Optuna 分数只来自 proxy；beauty 用于 Live Review / 人眼审查。
7. **定稿参数 = proxy Optuna 最优 trial**；`proxy_best.png` / `proxy_texture.png` 与该参数 **一一对应**（见 §4.1）。
8. 可选 `--use-vlm`：在 feature top-3 上对 **Beauty** 图打分，结果写入 `vlm_rerank_params`，**不覆盖**定稿参数。
9. `--texture-vlm-loop` 闭环对比 **`proxy_texture.png`**（非 beauty）。

```
feature = 0.28 × mean_similarity
        + 0.52 × structure（GLCM + Sobel）
        + 0.20 × direction_isotropy_match
```

（旧版仅 similarity + structure，易奖励有纹理但方向错误的 trial。）

### 6. 搜索空间（砂纹等 noise 类 finish）

| 参数 | 说明 | 默认 bounds（2026-06） |
|------|------|------------------------|
| `bump.strength` | 光学橘皮，极弱 | **0.02 – 0.10** |
| `micro.scale / detail` | 主颗粒尺度（≈200–400 μm 视觉） | scale **≥ 250**，detail 5–10 |
| `fine.scale / detail` | 细层 | scale 400–1800，detail 6–11 |
| `rough_mix_factor` | 程序化粗糙度混合 | 0.40 – 0.80 |
| `rough_ramp.to_min / to_max` | 空间粗糙度变化 | 0.40–0.72 / 0.62–0.90 |

`principled` 在纹理阶段 **锁定**（由 MaterialModule 产出），不在此重复搜索。

单阶段多变量 Optuna TPE；每 trial 保存完整 `full_params`。

### 7. 纹理类型与节点（生产侧）

| 纹理类型 | 节点 | 示例 finish |
|---------|------|-------------|
| 随机噪波 | M_Bakecoat Noise | outdoor_sand、flat_smooth |
| 细胞纹理 | Voronoi brush | burst_pattern |
| 方向纹理 | Wave / Voronoi + Anisotropic | gold_sweeping、brushed_aluminum |
| 复合 | 多层 Noise | microcrystalline |

纹理引擎当前默认 noise bakecoat 路径；拉丝/爆花等 brush 模式在 `material_calibrate_phases` 有专用搜索（`brush_mode`）。

### 8. 配置分层

```
texture_profiles/<id>.json      ← 纹理参数（TextureModule 主写入）
    ↑ texture_profile
finishes/<id>.json              ← principled + bakecoat 副本
catalog_colors.json             ← 颜色（独立维度）
```

`resolve_texture_profile_bakecoat()` 在渲染时合并 texture_profile → finish。

## 9. EEVEE 预览加速（`--texture-eevee-preview`）

纹理校准的 Optuna 搜索阶段默认使用 Cycles 渲染每个 trial。对于 50 trial 的搜索，总渲染时间约 50-60 分钟。

`--texture-eevee-preview` 将搜索分成两阶段：

### 两阶段流程

```
阶段 1（EEVEE Next, 快速）
  Optuna 50 trial 全部使用 EEVEE Next 渲染
  每个 trial ~1-3s（proxy） + ~2-5s（beauty）
  总时间 ~5 分钟

阶段 2（Cycles, 精调）
  自动切换到 Cycles
  围绕阶段 1 最优参数 ±5% 范围，8 trial 精调
  每个 trial ~15-30s，总时间 ~3-5 分钟

最终 export（beauty_best.png / proxy_best.png）
  始终使用 Cycles 渲染，保证交付质量
```

### 原理

纹理校准的平板场景极其简单——单个平面 + 两盏太阳灯，无复杂反射/折射/全局光照。EEVEE Next 在此场景下渲染质量与 Cycles 高度一致：

| 渲染类型 | 与 Cycles 差异 | 信任度 |
|---------|---------------|--------|
| **Proxy feature pass**（Emission 直出） | **≈0%** — Emission 计算引擎无关 | 完全可信 |
| **Beauty 结构评分**（LBP/GLCM/Sobel） | **极低** — LBP 对单调光度变化不变 | 高可信 |

评分函数（FFT 频域分析、Sobel 边缘密度、各向同性）基于 2D 图像特征，相对鲁棒。

### 精度保障

两阶段设计提供三层保障：

1. **EEVEE 粗搜索**：快速定位最优参数区域（~85% 概率直接命中全局最优）
2. **Cycles 精调**：围绕最优区域 ±5% 范围做少量精调，补偿引擎间系统性偏移
3. **最终 export**：始终使用 Cycles 高质量渲染，`beauty_best.png` 不受影响

### 使用方式

```powershell
cd blenderworker

# 新流程（推荐）
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --texture-eevee-preview `
  --texture-refine-cycles-trials 8

# 同时使用 VLM 闭环
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --texture-eevee-preview `
  --texture-vlm-loop

# 传统 Cycles-only（不受影响）
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png
```

### 新增 CLI 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--texture-eevee-preview` | `False` | 启用 EEVEE Next 加速搜索；不加此参数行为不变 |
| `--texture-refine-cycles-trials` | `8` | Cycles 精调 trial 数（仅 `--texture-eevee-preview` 时生效） |

### 实现

核心代码入口 `calibrate_texture_reference()`（`texture_engine.py`）：

```python
# 场景创建后，若启用 EEVEE 预览：
_setup_texture_eevee(client)          # EEVEE Next, 64 TAA samples

# Optuna 搜索完成（所有 trial 使用 EEVEE）

# 切换到 Cycles 精调：
_setup_texture_cycles(client, 256)    # Cycles, 256 samples, adaptive
# 在最优参数 ±5% 范围内，使用 random.Random(42) 产生扰动 trial
study.enqueue_trial(perturbed)
study.optimize(objective, n_trials=n_refine)

# 最终 export 始终使用 Cycles（export_texture_review_artifacts）
```

`_render_panel()` 中的 `cycles.samples` 访问已用 `try/except AttributeError` 包裹，在 EEVEE 引擎下自动跳过。

## 10. 纹理贴图提取管线（`--use-texture-map`）

### 10.1 动机

当前评分管线存在「评分双方不在同一域」的问题：

```
M_Bakecoat Feature_Signal (纯纹理, 无光照)  vs  蚁力色卡 crop (实物照片, 有光照/噪点/3D几何阴影)
```

虽然 `preprocess_reference()` 做了光照分离（high_low_separation），但实物照片的残留光照梯度、sensor 噪点、3D 微几何阴影无法完全去除。这导致 Optuna 有时收敛到「统计高分、人眼怪异」的解。

**方案 B 贴图轨**：先提取干净纹理贴图，再让程序化噪波去拟合贴图→两边都在纯纹理域里比较。

### 10.2 提取流程

```
蚁力色卡 crop
  │
  ├─ [内置模式] extract_texture_channels() + make_seamless_tile() + 去噪
  └─ [外部工具] DeepBump / Substance 3D Sampler / Materialize 等
  │
  ▼
outputs/yili_crops/<finish_id>/<finish_id>_texture_map.png
  │
  ▼
calibrate.py --scope texture --use-texture-map
  │
  ▼
M_Bakecoat 程序化噪波 → Feature_Signal → 对比贴图 → Optuna
```

### 10.3 命令行

```powershell
# 1. 提取贴图（内置模式）
python scripts/extract_texture_map.py --finish-id outdoor_sand

# 2. 提取贴图（外部工具，如 DeepBump 生成 roughness map）
python scripts/extract_texture_map.py --finish-id outdoor_sand --external path/to/map.png

# 3. 使用贴图作为参考重跑纹理校准
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --use-texture-map `
  --texture-trials 24 `
  --no-auto-write
```

### 10.4 提取质量保障

| 检查项 | 指标 | 内置模式 | 外部模式 |
|--------|------|---------|---------|
| 光照残留 | `baseline_flatness_std < 5.0` | ✅ QA 门控 | 假设已满足 |
| 无缝度 | `seam_intensity < 0.08` | ✅ `make_seamless_tile()` | 信任工具 |
| 结构保留 | `raw_vs_map_ssim > 0.65` | ✅ 对比原图 | 信任工具 |
| 高频噪声 | 高斯 sigma=0.5 | ✅ | 不处理 |

每个提取结果写入 `_texture_map_qa.json`，不达标的贴图不会被 calibrate 使用。

### 10.5 与现有评分的关系

| 方面 | 传统模式 (crop direct) | 贴图模式 (--use-texture-map) |
|------|----------------------|------------------------------|
| 参考预处理 | `preprocess_reference()`（高通+去梯度+去光照） | `preprocess_texture_map()`（仅归一化+轻量去噪） |
| 评分信号信噪比 | 低（光照残留+噪点） | 高（纯纹理域） |
| 适用场景 | 快速验证、首次校准 | 精调定稿、程序化天花板附近 |
| VLM 闭环对比 | proxy vs 实物照片 | proxy vs 干净贴图 |

## 与材质校准的关系

```
material_calibrate（球体）
  带 substrate_finish_id：合并拉丝铝 + 搜漆层 principled / coat
  无 substrate：Phase 1 plain BSDF → principled

texture_engine（平板 + 参考图）
  paint-only M_Bakecoat → 搜砂纹 + rough_mix（无 Voronoi 基材）
  Beauty 审查：完整 coat 栈 + dielectric 漆色，anisotropic=0
  生产 / 验收球：resolve_finish_cfg 全栈（铝拉丝 + 砂纹漆）
```

**不要**在 `--scope material` 默认路径上期望纹理收敛；砂纹/户外漆用 `--scope finish` 或 `--scope texture`。

### 校准 vs 生产（路径分离）

| 路径 | 基材 Voronoi | Coat 栈 | 用途 |
|------|-------------|---------|------|
| TextureModule proxy | ❌ paint-only | emission 特征 pass | Optuna 评分 |
| TextureModule beauty | ❌ paint-only | ✅ 完整 coat | Live Review / compare_beauty_pbr |
| `acceptance_finish` / `render.py` | ✅ | ✅ | 定稿验收 / 生产 |

## VLM 自主闭环（`--texture-vlm-loop`）

当 GLCM/诚实评分长期不达标时，可启用多轮闭环：

```
Round N: Optuna (--texture-trials) → 选 best proxy trial
       → VLM 对比 proxy vs 参考（overall_score + 文字反馈）
       → 根据反馈收紧/放宽 bounds（micro_scale、bump、rough_mix 等）
       → Round N+1 ...
```

| 产物 | 说明 |
|------|------|
| `texture_vlm_loop.json` | 各轮 Optuna 摘要、feature 分、VLM 分、bounds 变更 |
| `texture_vlm_loop.jsonl` | 逐 trial 日志 |

**注意**：pipeline 最终写入 preset 的 trial 由 VLM/Optuna 综合选出；若需按 **feature 最高轮** 写 preset，用 `scripts/write_feature_best_round.py <finish_id>`（读取 `texture_vlm_loop.json` 中各轮 `best_feature_score`）。

## 定稿验收

preset 写入后：

```powershell
python scripts/acceptance_finish.py --finish-id outdoor_sand
python scripts/write_feature_best_round.py outdoor_sand   # 可选：feature-best 轮覆盖 preset
python scripts/preview.py --finish outdoor_sand --texture outdoor_sand   # 生产模式，非 --calibration
```

| 产物 | 路径 |
|------|------|
| 金属球 | `calibrate_out/acceptance_<id>/shader_ball.png` |
| 平板三栏 | `calibrate_out/texture_<id>/compare_triple.png` |

## CLI

统一入口与 scope 说明见 [calibration_pipeline_design.md](./calibration_pipeline_design.md)。

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

# ── 仅纹理（PBR 已在材质球阶段或人工锁定）──
python scripts/calibrate.py `
  --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --texture-trials 10 `
  --use-vlm `
  --no-auto-write

# ── 纹理贴图提取 + 贴图参考校准（方案 B）──
# 完整工作流见 docs/texture_map_extraction_guide.md
python scripts/extract_texture_map.py --finish-id outdoor_sand
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --use-texture-map `
  --texture-trials 24 `
  --no-auto-write

# ── 推荐：材质球 + 纹理平板 一次性 ──
python scripts/calibrate.py `
  --scope finish `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --no-auto-write

# ── 全流程：材质 + 纹理 + 类目 ──
python scripts/calibrate.py `
  --scope full `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --model assets/guardrial.obj `
  --category aluminum_6063 `
  --no-auto-write

# 仅重导审查三栏图（不重新 Optuna）
python scripts/render_texture_review.py --finish-id outdoor_sand

# ── EEVEE 加速纹理校准（~10x 更快）──
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --texture-eevee-preview `
  --texture-refine-cycles-trials 8

# 归档上一轮 + 重跑 + 自动对比（产物 round_comparison.md）
python scripts/run_texture_cal_round.py `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --archive-label pre_isotropy_paint_only `
  --texture-trials 24 `
  --texture-vlm-max-rounds 1 `
  --live-review `
  --no-auto-write
```

| `--scope` | 本模块 | 说明 |
|-----------|--------|------|
| `texture` | ✅ 仅 TextureModule | 需 `--reference`（蚁力 crop） |
| `finish` | ✅ 第二步（接 Material） | 推荐 look-dev 主路径 |
| `full` | ✅ 第二步（接 Material，再接 Category） | 需 `--model` 才跑类目 |
| `material` | ❌ 不运行 | 球体不做 reference 纹理 |

兼容：`--mode texture` 等价于 `--scope texture`。

## 产物

| 路径 | 内容 |
|------|------|
| `calibrate_out/texture_<id>/trial_*.png` | 各 trial 平板渲染 |
| `calibrate_out/texture_<id>/trial_*_preview.png` | proxy 审查帧 |
| `calibrate_out/texture_<id>/trial_*_beauty.png` | beauty 审查帧 |
| `calibrate_out/texture_<id>/archive/<stamp>_*` | 上一轮归档 |
| `calibrate_out/texture_<id>/round_comparison.md` | 与归档轮次自动对比 |
| `calibrate_out/texture_<id>/vlm_*.png` | VLM 候选 |
| `texture_profiles/<id>.json` | bakecoat 模板 |
| `finishes/<id>.json` | bakecoat 同步写入 |

## 纹理校准效果评估

| finish 类型 | 当前方案 | 评估 | 后续方向 |
|-----------|---------|------|---------|
| 随机噪波类（outdoor_sand、flat_smooth、repair_spray、super_weather_resistant、premium_fluorocarbon） | Noise Texture | ⚠️ 合理可用，但非蚁力照片复刻 | ⬜ TODO：若需提升，考虑 Image Texture + Object 坐标方案 |
| 微晶结构类（microcrystalline） | Noise Texture | ⚠️ 勉强，规则感不足 | ⬜ TODO：需扩展 Voronoi 节点路径 |
| 花纹类（burst_pattern） | Noise Texture | ❌ 无法模拟辐射状花纹 | ⬜ TODO：需 Voronoi/Wave 节点路径 |
| 方向拉丝类（gold_sweeping） | Noise Texture | ❌ 无法模拟方向性拉丝 | ⬜ TODO：需 Wave + Anisotropic 节点路径 |

当前 Noise Texture 方案对 outdoor_sand 等随机噪波类 finish 已无提升空间。
结构纹理和方向纹理需要扩展节点类型（Voronoi/Wave）才能突破。

## 环境

- 宿主机 Blender TCP `:19876`
- 参考图先跑 `python scripts/crop_yili_references.py`（需 `outputs/蚁力色卡/` 原图）

## 进行中的待办

- **Phase 0（当前）**：outdoor_sand 端到端定稿 → [outdoor_sand_calibration_backlog.md](./outdoor_sand_calibration_backlog.md)
- **Phase 1+（暂缓）**：其余蚁力纹理、通用 bounds、brush 节点扩展 → [texture_calibration_roadmap.md](./texture_calibration_roadmap.md)
