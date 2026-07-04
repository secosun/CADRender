# outdoor_sand M_Bakecoat v2 实施计划

> **状态**：执行中（2026-06-26）  
> **前置**：target80 数值达标（composite≈0.998），G1 人眼未过 — 颗粒层次单一、边缘过锐、缺缺陷  
> **策略**：扩展 `M_Bakecoat` 节点组 + 校准维扩展；**不改 scene / 基材 Voronoi**；仍以 Beauty PBR 为 G1 准绳  
> **关联**：`docs/outdoor_sand_calibration_backlog.md`、`docs/texture_calibration_design.md`

---

## 1. 问题与目标

### 1.1 人眼差距（G1 审查）

| 维度 | 实拍 | 程序化（v1） | 优先级 |
|------|------|-------------|--------|
| 噪点层次 | 大/中/小混合、团簇感 | 几乎仅 micro bump | P0 |
| 边缘柔化 | 光学模糊、柔和 | Normal 硬边、CG 感 | P0 |
| 缺陷事件 | 偶发大颗粒/尘点 | 无 | P0 |
| 暗部加密 | 暗粗密、亮细腻 | roughness 有、bump 无亮度门控 | P1 |
| 方向性 | 轻微不规则 | 偶有伪竖纹 | P1 |
| 色彩渗透 | 微妙冷暖 | 灰蓝统一 | P2（本轮不做） |

### 1.2 v1 根因（代码）

- `_flat_params_to_bakecoat()` **强制** `fine_bump_enable=0`、`hyperfine_enable=0`，fine scale cap 为 `micro×3`
- `M_Bakecoat` 无 Voronoi 团簇 / 缺陷层；Mapping 无 Distort
- `Bump_Distance` 固定，亮暗区 bump 强度无分化
- Scorer 与眼睛：GLCM/Sobel 可高分，但不奖励团簇+柔边+稀疏缺陷

### 1.3 v2 目标

在 **iter#22 warm-start** 附近小范围搜索，使 G1 `compare_beauty_pbr.png` 通过：

- 可见 **大/中/小** 三层 bump 贡献（micro + fine + macro Voronoi）
- 颗粒边缘 **光学级柔化**（bump distance × softness）
- **~3–8%** 稀疏缺陷亮点
- 保持 paint-only、anisotropic=0、不写 preset（`--no-auto-write`）

---

## 2. 技术方案

### 2.1 M_Bakecoat 新增 Group Input

| 参数 | 默认（v1 兼容） | 作用 |
|------|----------------|------|
| `Fine_Bump_Weight` | 1.0 | fine bump 强度系数（配合 `Fine_Bump_Enable`） |
| `Macro_Cluster_Enable` | 0.0 | 宏团簇总开关 |
| `Macro_Cluster_Scale` | 12.0 | Voronoi F2−F1 尺度 |
| `Macro_Cluster_Weight` | 0.0 | 团簇高度权重 |
| `Macro_Cluster_Threshold` | 0.55 | 稀疏 mask 阈值 |
| `Defect_Enable` | 0.0 | 缺陷层开关 |
| `Defect_Scale` | 18.0 | 缺陷 Voronoi 尺度 |
| `Defect_Threshold` | 0.06 | 出现率（越小越稀） |
| `Defect_Strength` | 0.0 | 缺陷 bump 强度 |
| `Distort_Strength` | 0.0 | Mapping 向量扰动 |
| `Valley_Bump_Boost` | 0.0 | 噪声谷值区 bump 加密 |
| `Bump_Softness` | 1.0 | `Bump_Distance` 乘数（>1 柔边） |

**向后兼容**：全部新参数默认 0 或 1，旧 preset 行为不变。

### 2.2 节点拓扑（增量）

```
Mapping → [Distort: 3×Noise 位移] → tex_vec
                ├→ Noise Micro / Fine / Hyperfine
                ├→ Voronoi Macro (F2−F1) → MapRange → ×Weight → ADD
                └→ Voronoi Defect → LessThan → ×Strength → ADD
micro_fac → bump_ramp → (+ macro + defect) → Bump Micro
bump_gain × (1 + Valley_Bump_Boost × valley_ramp(micro_fac))
Bump_Distance × Bump_Softness → 各 Bump 节点
Fine bump: strength × Fine_Bump_Weight
```

### 2.3 校准维（v2 扩展）

在 v1 11 维基础上增加 7 维（Optuna）：

| 参数 | center（iter#22 推导） | bounds |
|------|------------------------|--------|
| `fine_bump_weight` | 0.28 | 0.15–0.42 |
| `macro_cluster_scale` | 12.0 | 8–18 |
| `macro_cluster_weight` | 0.08 | 0.04–0.14 |
| `defect_strength` | 0.04 | 0.02–0.08 |
| `distort_strength` | 0.12 | 0.05–0.22 |
| `bump_softness` | 1.6 | 1.2–2.2 |
| `valley_bump_boost` | 0.30 | 0.15–0.50 |

配置：`calibrate_configs/texture_outdoor_sand_v2.json`  
`bakecoat_v2: true`，`scoring: beauty_target80`，16 trials 快验 → 32 trials 定稿。

### 2.4 不改项（本轮）

- 基材 `brushed_aluminum_voronoi` / scene HDRI
- Beauty 合成 Defocus（避免 scorer 错位）
- Principled 色彩渗透（P2）
- preset 写入（G3 门控后）

---

## 3. 执行阶段

| 阶段 | 内容 | 验收 |
|------|------|------|
| **P0-文档** | 本文档 + `calibrate_configs/README` 补充 | 归档可查 |
| **P1-节点** | `master_node_groups.create_bakecoat_group` v2 | Blender 可建组 |
| **P2-接线** | `material_builders._attach_m_bakecoat_group` | preset 字段映射 |
| **P3-校准** | `texture_engine` + `texture_refine_config` v2 维 | 单测通过 |
| **P4-快验** | 16 trials，`--archive-label v2_smoke` | 报告 + compare 图 |
| **P5-G1** | 人眼审查清单（§4） | 通过 → G3 preset |
| **P6-定稿** | 32 trials（若 P4 近线） | `texture_target_success.json` |

---

## 4. G1 快速验证清单

- [ ] 放大可见 **团簇级** 大颗粒（macro Voronoi）
- [ ] 暗部噪点比亮部 **更密/更粗**（valley boost）
- [ ] 颗粒边缘 **柔和**，无 CG 硬点（softness≥1.4）
- [ ] 约 **3–8%** 孤立亮点/缺陷
- [ ] **无** 规则竖向扫描线
- [ ] 整体仍接近 outdoor_sand 灰蓝（色彩不过漂）

---

## 5. 命令

```powershell
# 快验（16 trials）
python scripts/run_texture_cal_round.py `
  --finish-id outdoor_sand `
  --reference "D:\咸阳\框架评审\CADRender\outputs\yili_crops\outdoor_sand\outdoor_sand_07.png" `
  --refine-config calibrate_configs/texture_outdoor_sand_v2.json `
  --archive-label v2_smoke `
  --texture-trials 16 --no-auto-write

# 定稿（32 trials，G1 近线后）
python scripts/run_texture_cal_round.py `
  ... --archive-label v2_final --texture-trials 32 --no-auto-write
```

---

## 6. 风险与回退

| 风险 | 缓解 |
|------|------|
| 新维过多、16 trial 不够 | 先 smoke；必要时 32 trial |
| macro/defect 过强 → 脏点 | `Defect_Strength` 上限 0.08；scorer 仍约束 GLCM |
| Distort 引入伪方向性 | 上限 0.22 + isotropy 仍在 target80 综合分 |
| 节点组重建破坏旧材质 | 新参数默认=0，等价 v1 |

**回退**：refine JSON 改回 `texture_outdoor_sand_beauty_only.json`；`ensure_master_groups` 新默认即 v1 行为。

---

## 7. 变更文件清单

| 文件 | 变更 |
|------|------|
| `docs/outdoor_sand_m_bakecoat_v2_plan.md` | 本文档 |
| `src/core/master_node_groups.py` | M_Bakecoat v2 节点 |
| `src/core/material_builders.py` | v2 参数接线 |
| `src/orchestration/calibration/texture_engine.py` | v2 维 + `_flat_params_to_bakecoat` |
| `src/orchestration/calibration/shared/texture_refine_config.py` | `bakecoat_v2` 透传 |
| `calibrate_configs/texture_outdoor_sand_v2.json` | v2 搜索配置 |
| `tests/test_texture_engine.py` | v2 单测 |

---

## 8. 归档索引

| 产物 | 路径 |
|------|------|
| v2 计划 | `docs/outdoor_sand_m_bakecoat_v2_plan.md` |
| v1 最优报告 | `calibrate_out/texture_outdoor_sand/texture_calibration_report.json` |
| v2 校准输出 | `calibrate_out/texture_outdoor_sand/`（archive `v2_*`） |
| G1 审查图 | `compare_beauty_pbr.png`、`beauty_best.png` |

---

## 9. v2_smoke 跑次记录（2026-06-26）

| 项 | 结果 |
|----|------|
| 状态 | exit 0，16 trials，~18 min |
| best_score | **0.440**（v1 iter 0.998） |
| composite_match | **0.773**（未达 0.80） |
| glcm_reach | **0.563**（v1 为 1.0；macro/defect 拉低结构分） |
| texture_sim | 0.944 |
| isotropy | 1.0 |
| 异常 | **16 trials 分数完全相同** → Optuna 无法分化；需 G1 目检 + 调 scorer/层强度 |
| 归档 | `archive_v2_smoke_20260626_015250` |

**下一步**：目检 `compare_beauty_pbr.png`；若团簇/柔边有改善则放宽 `glcm_floor` 或降 macro/defect 默认后再跑 32 trials。

---

## 10. v2.1 微调（2026-06-26，G1 反馈落地）

| 优先级 | 实现 | 位置 |
|--------|------|------|
| P0 大尺度不均匀 | Musgrave dirt × roughness（scale≈35, strength≈7.5%） | `M_Bakecoat` `Dirt_*` |
| P1 缺陷事件 | Voronoi F1 LessThan + noise 稀疏 mask | `_defect_spark_layer` |
| P2 边缘柔化 | bump_softness 默认 1.85；G1 compare 光学 blur 0.42px | 材质 + `_soften_beauty_optical` |
| P3 色彩渗透 | 暗冷/亮暖 coat tint mix 4% | `_attach_coat_color_bleed` |

验证：`python scripts/render_texture_review.py --finish-id outdoor_sand --reference ...`
