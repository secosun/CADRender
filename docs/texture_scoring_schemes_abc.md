# 纹理双图评分方案归档（A / B / C）

> **背景**：`outdoor_sand` 纹理校准存在两类审查图——  
> - **scorer view**（`compare_triple` 中栏）：M_Bakecoat `Feature_Signal` 自发光，Optuna 历史 objective  
> - **PBR 微距**（`compare_beauty_pbr.png`）：Cycles 真实 coat + 掠射光，**G1 外观验收**  
> 另：**roughness 伪彩色**（`compare_triple` 右栏）为诊断通道，不参与 Optuna。  
>  
> **归档日期**：2026-06-26 · 当前生产 scoring：**`beauty_a_lite`**（见 [texture_a_lite_rationale.md](./texture_a_lite_rationale.md)）

---

## 1. 核心矛盾（为何无法「高都高、低都低」）

| 维度 | scorer view | PBR 微距 |
|------|-------------|----------|
| 内容 | 纹理统计（频谱、GLCM、团簇） | 纹理 + 光照 + Fresnel + 几何 |
| 光照 | 无（Feature_Signal 自发光） | 有（G1 掠射/面光） |
| 评分 | 算法（`_score_render_vs_references` / `_score_beauty_target80`） | 算法 + **VLM 人眼** |
| 像素对比 | 与参考 swatch 特征对齐 | 与参考实拍 swatch 外观对齐 |

**结论**：两张图测量的是**不同子空间**；只能建立**映射/分层约束**，不能要求单一标量严格单调一致。

### 当前项目已观测的脱节

| 现象 | 含义 |
|------|------|
| beauty 特征分 ~0.99，VLM ~0.35 | **算法分 ≠ 人眼分**（Optuna 可过拟合统计指标） |
| roughness 伪彩色豹纹，PBR 仍「还行」 | 伪彩色只约束 roughness 子空间 |
| Round 1 VLM：「块状、对比过高」 | 方向性/斑块问题，特征分未敏感捕获 |

---

## 2. 方案 A：统一输入空间（PBR → 剥离光照 → 纹理比较）

### 2.1 定义

```
PBR 渲染 → Flat / 无光照 / 材质通道（Roughness·Bump·Normal）
         → 与 Reference swatch 做 SSIM / 特征相似度
         → 与 scorer view 共用同一套 metric
```

### 2.2 具体操作（工程映射）

| 步骤 | 代码落点 | 状态 |
|------|----------|------|
| Proxy scorer 渲染 | `_render_panel(..., feature_pass=True)` → `Feature_Signal` | ✅ 已有 |
| Beauty PBR 渲染 | `_render_beauty_g1_panel` | ✅ 已有 |
| **Beauty Flat 通道** | 新增：Cycles 关高光 / 渲 Albedo 或 Roughness 平面 | ❌ 未做 |
| 统一评分函数 | `mean_reference_texture_similarity` + GLCM 柱 | ✅ 已有，可复用 |
| Optuna objective | `0.5×beauty_flat + 0.3×beauty_pbr + 0.2×proxy` 等 | ❌ 未做 |

### 2.3 优点

- scorer 与 PBR **在同一纹理维度**可比，相关性可设计为单调
- Optuna 不易收敛到「统计满分、人眼怪异」
- roughness 伪彩色问题可通过 Flat Roughness 通道纳入同一 loss

### 2.4 缺点

- 需新增 1 条 Beauty 渲染 pass（Flat / 通道图），Blender 场景改动
- Flat 图仍不含 Fresnel——**不能替代** G1 PBR 验收，只能辅助搜索
- 实现量：约 1–2 天（渲染 pass + objective 合并 + 对比实验）

---

## 3. 方案 B：分层评分（各管一段 + 人工/VLM 刹车）

### 3.1 定义

| 层 | scorer / 算法负责 | PBR / 人眼负责 | 建议权重 |
|----|------------------|----------------|----------|
| 纹理结构 | 颗粒形态、密度、各向同性 | VLM 确认团簇/方向 | 40% |
| Roughness 幅度 | false color 统计 + ramp 约束 | PBR 光泽明暗 | 30% |
| 光照响应 | 不参与 | PBR + VLM 全责 | 30% |

统一公式（概念）：

```
总分 = w1·scorer_texture + w2·scorer_roughness + w3·human_pbr_score
```

人眼分建议用 **成对排序（A/B）** 而非绝对分，降低主观漂移。

### 3.2 工程映射（当前实现）

| 分层 | 已实现 | 缺口 |
|------|--------|------|
| 纹理结构 · 算法 | `_score_beauty_target80`（sim + glcm + sobel + isotropy） | 与 VLM 未校准 |
| 纹理结构 · 人眼 | G1 VLM loop，`review_mode=g1_beauty` | VLM prompt 持续迭代 |
| Roughness · 诊断 | `compare_triple` 右栏 false color | 未进 objective |
| Roughness · 参数 | v28：`rough_ramp 0.57–0.73`、`Rough_Output_Min/Max` | 已落地 |
| 光照响应 | 仅 PBR + VLM | 无 Flat 通道 |
| **双 gate** | `VLM ≥ 0.75 AND beauty_feature ≥ 0.80` | ✅ G1 loop |
| **混合 objective** | `beauty_hybrid`（proxy + beauty 加权） | 配置有，G1 loop 未启用 |

代码入口：

- Optuna：`texture_engine.calibrate_texture_reference` · `scoring=beauty_target80`
- VLM 循环：`texture_vlm_loop.run_texture_vlm_loop`
- 审查图：`texture_engine._compose_texture_compare`（triple）/ `compare_beauty_pbr`

### 3.3 优点

- **与当前流程一致**，无需新渲染 pass 即可运行
- VLM 充当 `human_pbr_score`，解决「算法高、人眼低」
- roughness 伪彩色 + VLM issue tag 可分工协作（已加 `roughness_overmodulated`）

### 3.4 缺点

- scorer 与 PBR **仍非同一空间**，两层算法分可能继续脱节
- VLM 成本高、有漂移，需稳定 prompt / 参考 framing
- Optuna 仍以 beauty 特征为主时，**搜索方向可能与人眼不一致**（已发生：0.99 vs 0.35）

---

## 4. 方案 C：端到端感知映射（长期）

### 4.1 定义

```
(PBR 图, scorer view, human_score) 三元组
    → 训练 Encoder：PBR → scorer 同维特征
    → 统一 perceptual loss（LPIPS 变体 / 小模型）
    → Optuna 直接优化统一 loss
```

### 4.2 前提与成本

| 项 | 要求 |
|----|------|
| 数据 | 数百组 `(params, proxy, beauty, human_rank)` |
| 标注 | 人工盲评或 VLM+人工校验 |
| 训练 | 离线 metric 学习，版本化 |
| 周期 | 数周–数月 |

### 4.3 定位

- **长期目标**：统一 scorer ↔ PBR ↔ 人眼
- **不适合**当前 outdoor_sand G1 冲刺

---

## 5. 三方案对比总表

| 维度 | A 统一空间 | B 分层评分 | C 端到端 |
|------|-----------|-----------|---------|
| 实现周期 | 1–2 周 | **已部分上线** | 数月 |
| **找到可用参数的概率** | **高** | **低–中** | 最高（有数据后） |
| 修复 Optuna↔人眼脱节 | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ |
| 修复 scorer↔PBR 算法脱节 | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ |
| G1 验收可信度 | 辅助 | **主路径（验收）** | 长期最优 |
| 依赖 VLM | 低 | **高** | 中（训练期） |
| 与现有代码契合 | 需新 pass | **流程已就绪** | 需新 infra |

---

## 6. A vs B：目前最适合哪一款？

### 6.1 结论（修订）

> **找参数靠 A，验收入口靠 B。**  
> B 单独跑很可能**找不到**同时满足人眼的参数；A（至少 A-lite）才是提高「搜到好解」概率的主路径。

| 角色 | 方案 | 说明 |
|------|------|------|
| **搜索（Optuna objective）** | **A** | 与 reference 在同一纹理空间优化，梯度/ TPE 有明确方向 |
| **验收（gate / 签字）** | **B** | VLM + PBR 微距，判断「能不能进 G1」 |

若资源只够做一个 PR：**优先 A-lite**，不是继续堆 B 的 VLM 轮次。

### 6.2 为什么 B 可能找不到参数

B 的本质是 **「用错误的目标函数搜索 + 用人眼事后纠偏」**：

```
Optuna 优化 beauty_target80  →  特征分 0.99（以为很好）
        ↓
VLM 评审 PBR              →  0.35（人眼否决）
        ↓
plan_next_search 调 bounds  →  启发式增减几个 knob
        ↓
下一轮 Optuna 仍优化 beauty_target80  →  循环，未必收敛
```

已发生案例（Round 1）：beauty **0.993** / VLM **0.35** / gate **False**。

| B 的结构性限制 | 后果 |
|----------------|------|
| objective 与 VLM 看的是不同空间 | 最优 trial 对人眼无意义 |
| VLM 只输出 increase/decrease/hold | 不能替代连续 loss 引导搜索 |
| bounds 逐轮收窄 | 可能把真最优排除在外 |
| 每轮 8 trials × 多轮 | 算力花在「错误目标」上 |

**B 能回答「这组参数能不能验收」；不能可靠回答「哪组参数最好」。**

### 6.3 为什么 A 更可能找到参数

A 让 Optuna 的每一步都在 **reference 纹理空间** 里有意义：

```
同一套 mean_reference_texture_similarity + GLCM/isotropy
    ↑                    ↑
proxy Feature_Signal   beauty Flat 通道（待加）
    └──────── 同维度 loss ────────┘
              ↓
         TPE 有连续反馈，朝「像 reference 纹理」收敛
              ↓
         再渲 PBR → VLM/B 验收（二次过滤）
```

| A 相对 B 的优势 | 说明 |
|----------------|------|
| 搜索目标 ≈ 参考 swatch 结构 | 与 outdoor_sand_07 对齐，非空转 |
| proxy 与 flat 可互相验证 | 减少「单通道过拟合」 |
| 不依赖 VLM 每轮在线 | 降低 API 成本与 prompt 漂移 |
| roughness 子空间可纳入 | Flat Roughness 通道直接约束豹纹 |

**A 不保证 PBR 一定好看**（还有 Fresnel/光位），但 **在参数空间里找到「纹理统计像 reference」的解的概率显著高于 B**。

### 6.4 决策表（修订）

| 判断问题 | 更适方案 | 理由 |
|----------|----------|------|
| **谁能帮 Optuna 找到好参数？** | **A** | 统一 loss；B 无此能力 |
| 谁能做 G1 签字验收？ | **B** | 只有 PBR + 人眼/VLM |
| Optuna 0.99 但 VLM 0.35 | **换 A objective** | 继续调 B 的 bounds 是绕圈 |
| roughness 豹纹 | **A**（Flat Roughness loss）+ B 诊断 | |
| 本周必须出 compare 图 | B loop 可并行 | 但不应指望它单独收敛 |

### 6.5 推荐落地顺序（修订）

```
Phase 0（已实现）— 方案 A-lite  ← 找参数
  · scoring=`beauty_a_lite`（`texture_outdoor_sand_vlm_g1.json`）
  · 每 trial：flat（beauty 栈 Feature_Signal）+ proxy + PBR 加权
  · 默认权重：0.50 / 0.30 / 0.20（`a_lite_*_weight` 可配）

Phase 1（并行）— 方案 B 作 gate  ← 验收入口
  · VLM ≥ 0.75 AND beauty_pbr ≥ 0.80（PBR 层，非 flat 层）
  · roughness 伪彩色人工/VLM 抽检

Phase 2 — B 强化（可选）
  · false color 绿橙占比 → roughness 子分
  · Top-K PBR 盲评

Phase 3 — 方案 C（长期）
  · 积累三元组 → 统一 metric
```

### 6.6 对「高都高、低都低」的预期（修订）

| 组合 | 找到好参数 | 验收一致 |
|------|-----------|---------|
| 仅 B | **低** | 中（gate 通过才可靠） |
| A-lite 搜 + B 验 | **高** | 中–高 |
| A + B + C | 最高 | 高 |

---

## 7. 相关文件索引

| 用途 | 路径 |
|------|------|
| Proxy 评分 | `blenderworker/src/orchestration/calibration/texture_engine.py` · `_score_render_vs_references` |
| Beauty 评分 | 同上 · `_score_beauty_target80` |
| 混合模式 | 同上 · `scoring_beauty_hybrid` |
| G1 VLM 循环 | `blenderworker/src/orchestration/calibration/shared/texture_vlm_loop.py` |
| 审查三联图 | 同上 · `_compose_texture_compare` → `compare_triple.png` |
| Beauty 验收图 | `compare_beauty_pbr.png` |
| G1 搜索配置 | `blenderworker/calibrate_configs/texture_outdoor_sand_vlm_g1.json` |
| v28 手工参数 | `blenderworker/calibrate_out/texture_outdoor_sand/v28_tuned_params.json` |
| 配置说明 | `blenderworker/calibrate_configs/README.md` |

---

## 8. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-26 | 初版：归档讨论中的 A/B/C，结合 outdoor_sand G1 现状给出 A vs B 建议 |
| 2026-06-26 | 修订 §6：明确 B 难找参数、A 搜索概率更高；A 主导搜索、B 主导验收 |
