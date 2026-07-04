# outdoor_sand 纹理校准待办

> 状态快照：2026-06-25  
> **阻塞级别**：🔴 **全项目最高风险 — 纹理必须先解阻塞**（仅 outdoor_sand，见下方顺序）  
> **范围**：Phase 0 完成前 **不做** 其余 finish、不做 category 救片式重标定。  
> **业务 KPI**：`模型 + finish + texture + category → HD 成片`（见 [roadmap §0–§1](./texture_calibration_roadmap.md)）  
> 设计变更：**paint-only + isotropy + Coat Normal**（见 [texture_calibration_design.md](./texture_calibration_design.md)）

---

## 纹理阻塞解除顺序（必须按序，不可跳步）

| 步 | 门控 | 动作 | 未通过则 |
|----|------|------|----------|
| **G1** | 平板审查 | 目检 `compare_triple.png` / `beauty_best.png`；proxy 无斜纹 | 不进入 G2；可调 Round 2 或贴图 A/B |
| **G2** | 表达路线 | **二选一定稿**：程序化 best（trial 19 一带）**或** 豆包无缝贴图 B 轨（产品 render 更优者） | 禁止写 preset |
| **G3** | Preset | `write_feature_best_round.py outdoor_sand`（或贴图 preset 手工写入） | — |
| **G4** | 全栈球 | `acceptance_finish.py` 金属球可接受 | 回 G2 查 coat/基材，**不调 scene** |
| **G5** | **解阻塞** | `render.py --model assets/guardrial.obj --category aluminum_6063` HD 成片人眼 PASS | 纹理仍阻塞；**禁止** category 大改救片 |
| **G6** | 可选 | 成片仅曝光/合成微调 → CategoryModule **小步** | 仍不得回改砂纹参数 |

**解阻塞判据**：G5 通过 = 纹理维对 outdoor_sand **可交付**；此后才启动 roadmap Phase 1（其余 finish）或 category 专项。

---

## 当前状态

| 轮次 | 说明 |
|------|------|
| Run7（历史） | Round 2 feature≈0.3667 曾写入 preset |
| `pre_isotropy_paint_only` 归档 | `archive/20260624_085447_*` — 含基材 Voronoi 旧轮 |
| **isotropy 轮（2026-06-24）** | Feature **0.495**（trial 19）；proxy VLM **0.15**；`round_comparison.md` 已生成 |
| **待做** | 目检定稿 → preset → 验收球 → **`render.py` 组合成片**；可选贴图 A/B |

**设计目标（蚁力参考）**：各向同性细砂纸橘皮 — 无优选方向、团簇状、光学 roughness 为主、bump 极弱。

---

## 2026-06 设计变更摘要

| 项 | 旧 | 新 |
|----|-----|-----|
| 纹理校准栈 | 合并 `substrate_brush`（Voronoi 拉丝） | **paint-only**，mapping `[1,1,1]` |
| Feature 分 | similarity + GLCM/Sobel | + **20% direction isotropy** |
| bump 搜索 | 0.04–0.22 | **0.02–0.10** |
| micro_scale 下限 | 可至 ~100 | **≥ 250** |
| Coat Normal | Blender 4 未接线 | **`GROUP` 类型修复 + paint_on_coat 直联** |
| Beauty 审查 | 强掠射、bump×2 | 弱梯度面积光、**与 proxy 同 bakecoat**、anisotropic=0 |
| Live Review | 先 beauty 后 proxy | **先 proxy ~20s，再 beauty** |
| 重跑工作流 | 手动清目录 | **`run_texture_cal_round.py` 归档 + 自动对比** |

---

## 待办清单

| # | 状态 | 任务 | 验收 / 备注 |
|---|------|------|-------------|
| 1 | ✅ 完成 | **isotropy 轮校准** | Feature 0.495；见 `round_comparison.md` |
| 2 | 🔄 **G1 阻塞** | **审查 compare_triple / beauty_best** | 中栏无斜纹；Beauty 颗粒可接受 |
| 2b | 🔄 **进行中** | **M_Bakecoat v2**（团簇/柔边/缺陷） | 见 `docs/outdoor_sand_m_bakecoat_v2_plan.md` |
| 3 | ⬜ **G2 阻塞** | **程序化 vs 贴图 A/B** | 同模型同场景选胜轨；**必做其一再写 preset** |
| 4 | ⬜ G3 | **写 preset** | `write_feature_best_round.py outdoor_sand` |
| 5 | ⬜ G4 | **验收金属球** | `acceptance_finish.py` |
| 6 | ⬜ **G5 解阻塞** | **HD 组合成片** | `render.py` guardrail；**纹理主验收** |
| 7 | ⬜ G6 可选 | 场景微调 | 仅 G5 通过后；**不改砂纹** |
| 8 | ✅ 完成 | **文档同步** | roadmap 含业务四维 + 调研对齐 |
| 9 | ⏸ 暂缓 | **其余 7 种蚁力纹理** | Phase 0 完成后 roadmap Phase 1 |

---

## 阶段一：纹理校准

### 看什么图

| 用途 | 路径 | 标准 |
|------|------|------|
| 纹理拟合（主依据） | `compare_triple.png` **中栏** proxy | 团簇橘皮，**无斜向拉丝** |
| 方向性 | 中栏 vs 左栏参考 | 各向同性，非 30–45° 条带 |
| 外观预览 | `beauty_best.png`、`compare_beauty_pbr.png` | paint-only coat，弱 bump 下可见颗粒 |
| 轮次对比 | `round_comparison.md` | vs `archive/` 上一轮 |
| Live Review | Beauty \| Proxy × 上一张 \| 当前 | **先 proxy 后 beauty** |

勿用 beauty 作 Optuna 评分；VLM 闭环看 **`proxy_texture.png`**。

### 命令

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

# 推荐：归档 + 校准 + 自动对比
python scripts/run_texture_cal_round.py `
  --finish-id outdoor_sand `
  --reference ..\outputs\yili_crops\outdoor_sand\outdoor_sand_crop.png `
  --archive-label pre_isotropy_paint_only `
  --texture-trials 24 `
  --texture-vlm-max-rounds 1 `
  --live-review `
  --no-auto-write

# 或直接 calibrate（不归档）
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ..\outputs\yili_crops\outdoor_sand\outdoor_sand_crop.png `
  --texture-trials 24 `
  --texture-vlm-loop --texture-vlm-max-rounds 3 `
  --live-review --no-auto-write

# 定稿
python scripts/write_feature_best_round.py outdoor_sand
python scripts/acceptance_finish.py --finish-id outdoor_sand
```

### 通过门槛

- Feature **≥ 0.40**（含 isotropy 项后口径与旧轮不可直接比，看 `round_comparison.md`）
- Beauty **isotropy 指标** 接近参考（见 `round_comparison.json` → `beauty_metrics`）
- GLCM：render ≥ ref 的 **50%**
- VLM proxy vs 参考：overall **≥ 0.55** 为可接受，**≥ 0.72** 为闭环 pass

### 未达标时的旋钮

1. 确认 **paint-only**（无 Voronoi 斜纹）
2. 提高 `micro_scale`（250–450），降低 `bump_strength`（≤ 0.06）
3. 检查 `round_comparison.md` 中 isotropy 是否上升
4. 隔离：`python scripts/test/diag_snowflake_isolate.py --finish-id outdoor_sand`

---

## 阶段二：finish 串联（纹理 PASS 后）

```powershell
python scripts/calibrate.py --scope finish `
  --finish-id outdoor_sand `
  --reference ..\outputs\yili_crops\outdoor_sand\outdoor_sand_crop.png `
  --live-review

python scripts/render.py --model assets/guardrial.obj --category aluminum_6063
```

- 球体：PBR + 拉丝（MaterialModule）
- 平板：砂纹 paint-only 校准；生产 render 为全栈

---

## 成功标准（对外）

**组合 KPI**（优先于单一 Feature / proxy VLM）：

```
guardrail（或标准件） + outdoor_sand finish + texture + aluminum_6063 category
→ 高清效果图 ≈ 蚁力 outdoor_sand 预期
```

**纹理维**（平板审查）：

- Proxy 中栏：团簇尺度、密度接近蚁力参考，**无方向性伪影**
- Beauty：完整 coat 下可见细砂面，非斜拉丝
- Feature ≥ 0.40（isotropy 口径）；**不以 proxy VLM 0.72 为唯一硬门槛**

**定稿与验收**：

- preset 写入 `finishes/outdoor_sand.json` + `texture_profiles/outdoor_sand.json`（程序化或贴图胜轨）
- 验收球 `acceptance_outdoor_sand/shader_ball.png` 可接受
- **`render.py` 标准模型 HD 成片** 人眼可接受

---

## 相关文档

- [texture_calibration_roadmap.md](./texture_calibration_roadmap.md) — **业务四维 + 攻关优先级**
- [texture_calibration_design.md](./texture_calibration_design.md)
- [material_calibration_guide.md](./material_calibration_guide.md)
- [calibration_pipeline_design.md](./calibration_pipeline_design.md)
