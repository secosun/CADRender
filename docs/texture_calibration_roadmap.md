# 纹理校准推进路线图

> **归档日期**：2026-06-24（2026-06-25 增补：业务四维公式、调研报告对齐、纹理双轨）  
> **2026-07 修订**：纹理贴图提取管线（方案 B）落地为 `extract_texture_map.py` + `--use-texture-map`，从蚁力 crop 提取干净贴图作为程序化拟合目标，提升评分信噪比。  
> **当前策略**：**纹理是当前最大风险与唯一阻塞项 — 必须先解决 `outdoor_sand` 纹理定稿**，再动场景批量与其余 finish。  
> **关联文档**：[texture_calibration_design.md](./texture_calibration_design.md)（设计思想）、[outdoor_sand_calibration_backlog.md](./outdoor_sand_calibration_backlog.md)（**唯一执行清单**）、调研报告 `Blender照片转程序化纹理技术调研报告.docx`

---

## 0. 风险与阻塞（2026-06-25）

四维 catalog 出图中，**纹理维风险最高、阻塞整链**：

| 维度 | 成熟度 | 风险 | 说明 |
|------|--------|------|------|
| 模型 | 中–高 | 低 | 参数化 mesh 可出图 |
| **材质** | 中 | 中 | 球体 PBR + 铝基材已可锁；依赖纹理定稿后全栈验收 |
| **纹理** | **低** | **最高** | Feature/VLM 分裂、程序化天花板、产品成片未 PASS |
| 场景 | 中 | 低–中 | **纹理未定稿前不调 category**，避免用曝光掩盖砂纹问题 |

**阻塞定义**：在 **`render.py` 标准模型 HD 成片** 上，outdoor_sand 砂纹 **人眼可接受** 且 preset 已写入之前，视为纹理 **未解阻塞**。

**冻结项（纹理阻塞期间不做）**：

- 其余 7 种蚁力纹理批量校准  
- Category 大范围重标定 / 曝光「救片」  
- 可微渲染研究线（Mitsuba 等）  
- 非 outdoor_sand 相关的材质大改  

**唯一攻关路径**：见本文 §4 Phase 0 + [outdoor_sand_calibration_backlog.md](./outdoor_sand_calibration_backlog.md) **「纹理阻塞解除顺序」**。

---

## 1. 业务目标（catalog 出图公式）

CADRender 的业务产出不是「单张纹理拟合最优」，而是 **参数化 catalog 的稳定高清效果图**：

```
高清效果图 = 参数化模型 × 可选材质(finish) × 可选纹理(texture) × 场景(category/scene)
```

| 维度 | 预设载体 | 校准模块 | 生产入口 |
|------|----------|----------|----------|
| **模型** | CAD/FreeCAD → mesh | （几何侧，非本管线） | `render.py --model` |
| **材质** | `finishes/*.json`（principled、coat、`substrate_finish_id`） | MaterialModule（球体） | finish / catalog 颜色 |
| **纹理** | `texture_profiles/*.json` 或 Image maps | TextureModule（平板） | `texture_profile` 引用 |
| **场景** | category preset（灯光、曝光、合成） | CategoryModule（产品） | `render.py --category` / `--scene` |

**组合验收 KPI**（Phase 0 定稿标准，优于单一 Feature / proxy VLM 分）：

```
标准参数化模型 + outdoor_sand finish + outdoor_sand texture + 已定 category
→ 高清成片 ≈ 蚁力色卡预期（人眼）
```

纹理平板 PASS **不等于** 业务 PASS；必须在 **代表产品模型 + 场景** 上复验。

**架构约束**（服务参数化模型）：

1. **纹理与模型解耦**：优先 Object 坐标或稳定 UV，不绑定单一 mesh。  
2. **纹理与材质解耦**：`texture_profile` 可换；finish 管 PBR/基材。  
3. **场景独立调光**：成片偏亮/偏平 → CategoryModule，**不回改砂纹参数**。  
4. **纹理双实现、统一 catalog 接口**：对外均为「选 outdoor_sand 纹理」，对内可 procedural 或 image。

---

## 2. 策略摘要

本方案在 **流程与架构** 上具有通用性，在 **搜参与评分** 上当前是 **「各向同性 M_Bakecoat 砂纹」** 的专用实例（以 outdoor_sand 为原点）。

```
通用校准框架（长期标准）
  ├── 参考图 + 平板 + Proxy/Beauty 双 pass
  ├── 校准 paint-only、生产/验收全栈
  ├── Material → Texture → Category 分阶段
  ├── Optuna + 可选 VLM + Live Review + 归档对比
  └── texture_profiles 独立写入

当前专用插件（outdoor_sand 标杆）
  ├── M_Bakecoat 噪波搜参（bump / micro / fine / rough_mix）
  ├── Feature 含 20% direction isotropy 惩罚
  ├── sand 专用 bounds（bump 0.02–0.10，micro_scale ≥ 250）
  └── Beauty 审查：与 proxy 同 bakecoat；anisotropic=0、弱梯度光（仅 PBR pass 不同）
```

**决策**：先以 outdoor_sand 把专用插件跑通并定稿 preset；再按 finish 类型复制框架、替换 bounds/评分/节点路径。

---

## 3. 通用性分层（归档）

### 3.1 强通用 — 可直接复用

| 能力 | 说明 |
|------|------|
| 两阶段管线 | 球体 MaterialModule 定 PBR；平板 TextureModule 定纹理 |
| 参考图驱动 | `--reference` 硬约束；无参考图拒绝启动 |
| Proxy / Beauty 分离 | Optuna 仅 proxy roughness emission；Beauty 供人眼/VLM |
| paint-only vs 全栈 | 校准剥离基材 Voronoi；`acceptance_finish` / `render.py` 仍全栈 |
| 配置分层 | `texture_profiles` + `finishes` + `catalog_colors` |
| 工具链 | `run_texture_cal_round.py`、`write_feature_best_round.py`、Live Review、VLM 闭环 |
| Coat Normal 修复 | Blender 4.x `GROUP` + `paint_on_coat`；所有喷漆 finish 生产路径受益 |

### 3.2 部分通用 — 噪波类 finish，需调 bounds

与当前 `texture_engine` **节点路径一致**（M_Bakecoat Noise + rough_mix），换 `--finish-id` + reference 即可启动，但 **不能照搬 outdoor_sand 的 bounds**：

| finish | 与 sand bounds 的差异 |
|--------|----------------------|
| `repair_spray` / `super_weather_resistant` / `premium_fluorocarbon` | 结构类似，微调 bump / micro 区间即可 |
| `flat_smooth` | preset bump≈0.012，低于当前下限 0.02；micro/fine 常为空 |
| `microcrystalline` | 能搜参，但 Noise 规则感不足，质量上限低 |
| `burst_pattern` | 旧 preset bump≈0.13、micro≈1200，超出 sand 假设；且缺径向花纹节点 |

**代码锚点**：`_param_bounds()` 在 `texture_engine.py`，当前写死 sand 区间。

### 3.3 专用 / 需扩展 — 不宜直接套用

| 项 | 适用 | 不适用 |
|----|------|--------|
| **20% isotropy 惩罚** | 各向同性砂纹（outdoor_sand） | `gold_sweeping` 等有意方向性纹理 |
| **Beauty anisotropic=0** | 砂纹审查 | 扫金、拉丝类 |
| **M_Bakecoat 单路径** | 随机噪波漆 | 爆花（Voronoi 径向）、扫金（Wave + Aniso） |

设计文档已标注节点表达力上限（见 [texture_calibration_design.md §7](./texture_calibration_design.md)）。`material_builders.py` 已有 `voronoi_brush` / `wave_brush`，但 **TextureModule 尚未接入 brush 搜参**。

---

## 4. 分阶段推进

### Phase 0 — 当前焦点：`outdoor_sand` 定稿（阻塞项）

**目标**：在 **四维组合** 下闭环 — 纹理 preset → 金属球验收 → **标准模型 HD 成片**。

**执行清单**（细节见 [outdoor_sand_calibration_backlog.md](./outdoor_sand_calibration_backlog.md)）：

| # | 任务 | 验收 |
|---|------|------|
| 0.1 | isotropy + paint-only 轮校准 | `round_comparison.md`；Feature ≥ 0.40；proxy 无斜纹 |
| 0.2 | 审查 compare_triple / beauty_best | 中栏团簇橘皮 ≈ 参考 |
| 0.3 | **纹理双轨 A/B**（可选） | 程序化 best vs 豆包/AI 无缝贴图；同模型同场景人眼选胜 |
| 0.4 | 写 preset | `write_feature_best_round.py outdoor_sand`（或贴图胜出的 preset） |
| 0.5 | 金属球验收 | `acceptance_finish.py`（**全栈**，非 paint-only） |
| 0.6 | **组合验收** | `render.py --model assets/guardrial.obj --category aluminum_6063` 成片 |

**不在此阶段做**：其余 7 种纹理批量、Mitsuba 可微拟合、全库架构重写。

---

### Phase 1 — 噪波类批量（outdoor_sand 定稿后）

**前提**：Phase 0 验收通过；`run_texture_cal_round.py` 模板已验证。

**范围**（M_Bakecoat Noise，流程 100% 复用）：

| finish | 优先级 | 备注 |
|--------|--------|------|
| `repair_spray` | P1 | 与 sand 最接近 |
| `super_weather_resistant` | P1 | 同上 |
| `premium_fluorocarbon` | P1 | 同上 |
| `flat_smooth` | P2 | 需放宽 bump 下限、允许空 micro |
| `microcrystalline` | P3 | 先跑通流程，质量可能需 Phase 2 节点扩展 |

**每 finish 最小步骤**：

1. 准备蚁力 reference crop（`scripts/crop_yili_references.py`）
2. `--scope finish` 或 `run_texture_cal_round.py`（归档 + 对比）
3. Live Review + 可选 VLM 1 轮
4. `write_feature_best_round.py` → `acceptance_finish.py`

**Phase 1 前需做的工程**（小改，非阻塞 outdoor_sand）：

- [ ] `texture_profiles/<id>.json` 或 finish JSON 增加可选 `calibration.bounds_override`
- [ ] isotropy 权重可配置（flat_smooth 可降至 0）

---

### Phase 2 — 节点与评分扩展（花纹 / 方向类）

**范围**（当前 M_Bakecoat 噪波 **无法** 表达）：

| finish | texture_class（建议） | 需扩展 |
|--------|----------------------|--------|
| `burst_pattern` | `radial_voronoi` | Voronoi 径向 pattern + 专用 bounds |
| `gold_sweeping` | `directional_brush` | Wave/Aniso + 方向一致评分（非 isotropy 惩罚） |

**Phase 2 工程项**：

- [ ] finish / texture_profile 增加 `texture_class` 字段
- [ ] `texture_engine` 按 class 分支：noise | voronoi_brush | wave_brush
- [ ] 每 class 一套 `_param_bounds()` + feature 权重表
- [ ] Beauty 审查 profile（方向类勿强制 `anisotropic=0`）

---

### Phase 3 — 贴图轨与表达力上限

**纹理维双轨**（服务「可选纹理」）：

| 轨道 | 实现 | 适用 |
|------|------|------|
| **A 程序化** | `build_bakecoat_principled` + M_Bakecoat | 低内存、Object 重复、已 Optuna 校准 |
| **B 贴图** | `build_texture_pbr_material` + Image + M_PBR_Core | 豆包/AI 无缝图、调研报告 **方案 1** |

#### Phase 3a — 纹理贴图提取（2026-07 新增）

从蚁力色卡 crop 提取干净纹理贴图作为程序化拟合的评分目标：

```
crop → extract_texture_map.py → _texture_map.png → calibrate.py --use-texture-map → Optuna → preset
```

| 机制 | 说明 |
|------|------|
| 内置提取 | `extract_texture_channels()` + `make_seamless_tile()` + 去噪 + QA 门控 |
| 外部工具 | `--external` 接入 DeepBump / Substance 3D Sampler 输出 |
| 评分 | 贴图已经去光照/去噪，走 `preprocess_texture_map()`（轻量归一化） |
| 定稿 | 提取贴图 fit 最优的程序化参数仍写入 preset（保留程序化优势） |

#### Phase 3b — Image Texture 直出（原有）

贴图通道规范：**勿**同一张 JPEG 同时作 Base Color / Roughness / Bump；coat 以 **Roughness + 极弱 Normal** 为主。

若 Phase 1 程序化仍不达标：优先 **B 轨 A/B 定稿**，而非无限加 Optuna trial。可选：更高分辨率 reference / 多 crop 融合。

---

## 5. 与调研报告对齐的攻关优先级

对照《Blender照片转程序化纹理技术调研报告》与当前 Optuna 方案：

| 报告档位 | 含义 | CADRender 决策 |
|----------|------|----------------|
| 方案 1 AI/工具提 **位图** | DeepBump、豆包无缝图等 | **Phase 0 并行 spike**：B 轨贴图 + 产品 render A/B |
| 方案 2 AI 图 + 投射/混合 | UV/Object 贴合 | 型材 **Object 平铺**；与 M_Bakecoat 可分层 |
| 方案 3 纯手工程序化 | Noise/Voronoi 节点 | **已走**：M_Bakecoat + TextureModule |
| 可微拟合（AI 目标 + Loss + 反传） | Mitsuba/PyTorch3D | **研究备线**；Cycles 不可微，Phase 0 **不投入** |

**近期重点（按业务公式排序）**：

| 优先级 | 轨道 | 内容 |
|--------|------|------|
| **P0** | 组合闭环 | outdoor_sand 纹理定稿 + `render.py` 标准模型成片验收 |
| **P1** | 纹理 B 轨 | 豆包无缝图 → coat Image Texture；与程序化 A/B |
| **P2** | 校准增强 | 多 swatch（已有）、VLM/审查对齐 Beauty 与产品 render；可选 VLM Round 2 |
| **P3** | Phase 1 批量 | 5 种噪波漆，冻结纹理模板后复制 |
| **P4** | 研究 | 可微程序化拟合试点（仅当 P0+P1 仍不达标） |

**明确不以 proxy VLM 0.72 作为唯一硬门槛**；以 **组合态人眼 + 产品 HD 成片** 为准。

---

## 6. finish 适用矩阵（归档）

| finish | 框架复用 | Phase 0 后可直接跑 | 预期质量 | 阶段 |
|--------|----------|-------------------|----------|------|
| **outdoor_sand** | ✅ | ✅ | **标杆** | **Phase 0（当前）** |
| repair_spray | ✅ | ✅ | 中–高 | Phase 1 |
| super_weather_resistant | ✅ | ✅ | 中–高 | Phase 1 |
| premium_fluorocarbon | ✅ | ✅ | 中–高 | Phase 1 |
| flat_smooth | ✅ | ⚠️ 调 bounds | 中 | Phase 1 |
| microcrystalline | ✅ | ⚠️ | 低–中 | Phase 1 → 可能 Phase 2 |
| burst_pattern | ✅ | ⚠️ | 低（节点不对） | Phase 2 |
| gold_sweeping | ✅ | ❌ | 低（节点+评分不对） | Phase 2 |

---

## 7. 命令模板（Phase 1 起复用）

Phase 0 命令见 [outdoor_sand_calibration_backlog.md](./outdoor_sand_calibration_backlog.md)。

Phase 1 批量时仅替换 `--finish-id` 与 `--reference`：

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

python scripts/run_texture_cal_round.py `
  --finish-id <finish_id> `
  --reference ..\outputs\yili_crops\<finish_id>\<finish_id>_crop.png `
  --archive-label pre_first_cal `
  --texture-trials 24 `
  --texture-vlm-max-rounds 1 `
  --live-review `
  --no-auto-write
```

定稿后：

```powershell
python scripts/write_feature_best_round.py <finish_id>
python scripts/acceptance_finish.py --finish-id <finish_id>
```

---

组合验收（Phase 0 必做）：

```powershell
python scripts/render.py --model assets/guardrial.obj --category aluminum_6063
```

---

## 8. 文档索引

| 文档 | 用途 |
|------|------|
| [texture_calibration_design.md](./texture_calibration_design.md) | 设计思想、Proxy/Beauty、评分公式 |
| [outdoor_sand_calibration_backlog.md](./outdoor_sand_calibration_backlog.md) | **Phase 0 唯一执行清单** |
| [texture_calibration_roadmap.md](./texture_calibration_roadmap.md) | **本文 — 业务四维 + 通用性 + 分阶段 + 调研对齐** |
| [calibration_pipeline_design.md](./calibration_pipeline_design.md) | 三模块总览 |
| [material_calibration_guide.md](./material_calibration_guide.md) | 实操命令 |

---

## 9. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-24 | 初版：通用性分析归档；确立 Phase 0 仅 outdoor_sand；Phase 1/2 分 finish 类型推进 |
| 2026-06-25 | 增补：业务四维公式、组合验收 KPI、纹理双轨、调研报告攻关优先级 |
| 2026-06-25 | **纹理标为最高风险阻塞项**；冻结 category 批量与其余 finish 直至 outdoor_sand 成片 PASS |
