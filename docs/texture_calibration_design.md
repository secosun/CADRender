# 纹理校准设计思想

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

生产材质节点：**Voronoi 拉丝（Anisotropic）+ M_Bakecoat 砂纹（Coat Normal / Roughness）** 同栈叠加。

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

### 4. 纹理平板 + 掠射光场景

| 要素 | 说明 |
|------|------|
| 几何 | `CalPanel` 平面（约 0.3×0.4 m），与色块平面一致 |
| 相机 | 低仰角（~84°），掠射观察 |
| 灯光 | Area Key（强）+ 弱 Fill；暗世界光 |
| 目的 | 让 bump / rough_mix 产生可见明暗，否则特征提取无信号 |

材质球场景 **不用于** 纹理校准。

### 5. 对称特征评分 + 可选 VLM

**问题 A（评分域）**：若只对参考图做高通、渲染 beauty pass 不做，Optuna 在比「光照」而非「纹理」。

**问题 B（beauty pass 平坦）**：高 `rough_mix` 哑光 finish 的 beauty 图在平板上几乎均匀灰度，Optuna 无信号。

**做法**：

1. 参考图与 trial 图 **同一套** `preprocess_reference` 后再提取特征。
2. **Optuna 主评分使用 roughness 代理 pass**（micro/fine Noise + `rough_mix` + `rough_ramp` → Emission），与 `M_Bakecoat` 参数对齐、与光照解耦；trial 图应可见颗粒结构。
3. 写入生产仍走完整 `build_bakecoat_principled` + `M_Bakecoat`。
4. 可选 `--use-vlm` 在 top-3 上精调。

```
score = 0.85 × cosine_similarity(features_render, features_ref)
      + 0.15 × texture_richness_norm
```

校准平板另设：`coat_weight=0`、Triplanar mapping、点光源（辅助预览）。

### 6. 搜索空间（砂纹等 noise 类 finish）

| 参数 | 说明 |
|------|------|
| `bump.strength` | 全局凹凸 |
| `micro.scale / detail` | 主颗粒尺度 |
| `fine.scale / detail` | 细层 |
| `rough_mix_factor` | 程序化粗糙度混合（砂纹视觉核心） |
| `rough_ramp.to_min / to_max` | 空间粗糙度变化范围 |

`principled` 在纹理阶段 **锁定**（由 MaterialModule 产出），不在此重复搜索。

单阶段多变量 Optuna TPE；每 trial 保存完整 `full_params`，避免分 phase 丢参。

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

## 与材质校准的关系

```
material_calibrate（球体）
  带 substrate_finish_id：合并拉丝铝 + 搜漆层 principled / coat
  无 substrate：Phase 1 plain BSDF → principled

texture_engine（平板 + 参考图）
  锁定 principled → 搜 bakecoat 砂纹 + rough_mix
  Beauty 审查（有基材时）保留 metallic/coating，非纯灰非金属板
```

**不要**在 `--scope material` 默认路径上期望纹理收敛；砂纹/户外漆用 `--scope finish` 或 `--scope texture`。

## CLI

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

# 仅纹理
python scripts/calibrate.py `
  --scope texture `
  --finish-id outdoor_sand `
  --reference outputs/yili_crops/outdoor_sand_crop.png `
  --texture-trials 50 `
  --use-vlm `
  --no-auto-write

# 推荐：材质 + 纹理
python scripts/calibrate.py `
  --scope finish `
  --finish-id outdoor_sand `
  --reference outputs/yili_crops/outdoor_sand_crop.png `
  --no-auto-write
```

兼容：`--mode texture` 等价于 `--scope texture`。

## 产物

| 路径 | 内容 |
|------|------|
| `calibrate_out/texture_<id>/trial_*.png` | 各 trial 平板渲染 |
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
