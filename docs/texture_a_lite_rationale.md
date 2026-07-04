# A-lite 方案说明与归档

> **状态**：已实现并启用 · `scoring: beauty_a_lite`  
> **配置**：`blenderworker/calibrate_configs/texture_outdoor_sand_vlm_g1.json`  
> **代码**：`texture_engine._combine_a_lite_score` · `calibrate_texture_reference(scoring_beauty_a_lite=True)`

---

## 1. 为什么 A-lite 更好（相对纯 B / 纯 beauty_target80）

### 1.1 纯 B（beauty_target80 + VLM gate）的根本问题

```
Optuna 优化目标 = PBR 算法特征分（beauty_target80）
人眼/VLM 验收   = 真实 PBR 微距外观
```

Round 1 实测：**beauty 0.993 / VLM 0.35** —— 搜索认为「已完美」，人眼认为「块状、对比过高」。

| 问题 | 后果 |
|------|------|
| objective 与 VLM 不同空间 | TPE 朝错误方向收敛 |
| VLM 只能调 bounds（增/减/保持） | 无法替代连续 loss 引导 |
| 每轮 8 trials 仍优化同一错误标量 | 算力空转 |

**B 能验收，不能可靠找参数。**

### 1.2 A-lite 解决什么

把 **80% 搜索权重** 放回与 reference swatch **同一纹理空间**（Feature_Signal + 同一套 `_score_render_vs_references`），只留 **20%** 给 PBR 结构分，VLM 仍作最终 gate。

```
每 trial：
  flat  (0.50) — beauty 材质栈 + Feature_Signal → 纹理 scorer
  proxy (0.30) — panel 代理 + Feature_Signal   → 纹理 scorer（交叉验证）
  pbr   (0.20) — G1 Beauty PBR                 → beauty_target80
        ↓
  composite = 加权合成分（Optuna 最大化）
        ↓
  VLM gate：PBR 子分 ≥ 0.80 且 VLM ≥ 0.75（B 层，不替代搜索）
```

### 1.3 五条具体好处

| # | 好处 | 机制 |
|---|------|------|
| 1 | **搜索有方向** | flat/proxy 与 reference 逐 trial 可比，TPE 每步有纹理反馈 |
| 2 | **不易过拟合 PBR 统计** | 80% 权重在纹理空间，避免「数值 0.99、看着怪」 |
| 3 | **双通道纹理互证** | flat（beauty 栈）+ proxy（panel 栈）同 bakecoat，降低单通道假最优 |
| 4 | **保留 G1 验收链** | PBR 20% + VLM gate 仍看人眼；composite 高 ≠ 自动签字 |
| 5 | **与现有资产兼容** | 复用 Feature_Signal 渲染与 scorer，无需新神经网络（对比方案 C） |

### 1.4 与纯 A / 纯 B 的定位

| 方案 | 找参数 | G1 验收 |
|------|--------|---------|
| 纯 B（beauty_target80） | 低 | 有 VLM |
| **A-lite** | **高** | 有 VLM + PBR 子分 gate |
| 纯 A（仅 flat/proxy） | 高 | 缺光照/Fresnel，不能单独验收 |
| C（端到端 metric） | 最高（需数据） | 长期 |

**A-lite = A 的搜索能力 + B 的验收门禁。**

---

## 2. 实现规格

### 2.1 权重（可配）

```json
{
  "scoring": "beauty_a_lite",
  "a_lite_flat_weight": 0.50,
  "a_lite_proxy_weight": 0.30,
  "a_lite_pbr_weight": 0.20
}
```

权重自动归一化；三者之和不必严格等于 1。

### 2.2 双 gate（VLM loop）

| 条件 | 阈值 | 用途 |
|------|------|------|
| composite（a_lite） | Optuna 选 best | **搜索** |
| `beauty_pbr_score` | ≥ 0.80 | **验收**（非 composite） |
| VLM | ≥ 0.75 | **验收** |

### 2.3 产物

| 文件 | 含义 |
|------|------|
| `trial_XXXX.png` | proxy Feature_Signal |
| `trial_XXXX_flat.png` | flat Feature_Signal（beauty 栈） |
| `trial_XXXX_beauty.png` | G1 Beauty PBR |
| `compare_beauty_pbr.png` | G1 外观验收主图 |
| `compare_triple.png` | ref \| proxy \| roughness 伪彩色 |
| `texture_vlm_loop.json` | 每轮 flat/proxy/pbr 分项 + gate |

### 2.4 性能

每 trial **3 次渲染**（proxy + flat + beauty），约为纯 beauty_only 的 **2–3×** 耗时。

---

## 3. 启动命令

```powershell
Set-Location "D:\咸阳\框架评审\CADRender\blenderworker"
$env:PYTHONPATH="D:\咸阳\框架评审\CADRender\blenderworker\src"
d:\blender-mcp\.venv\Scripts\python.exe scripts\calibrate.py `
  --scope texture --finish-id outdoor_sand `
  --reference "D:\咸阳\框架评审\CADRender\outputs\yili_crops\outdoor_sand\outdoor_sand_07.png" `
  --texture-vlm-loop --texture-vlm-max-rounds 10 --texture-trials 8 `
  --texture-refine-json calibrate_configs\texture_outdoor_sand_vlm_g1.json `
  --texture-vlm-pass-score 0.75 --texture-vlm-beauty-pass-score 0.80 `
  --no-auto-write
```

---

## 4. 相关文档

- [texture_scoring_schemes_abc.md](./texture_scoring_schemes_abc.md) — A/B/C 全方案对比
- [material_calibration_guide.md](./material_calibration_guide.md) — 材质/纹理校准总指南
- `blenderworker/calibrate_configs/README.md` — refine JSON 字段说明

---

## 5. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-26 | 初版：A-lite  rationale + 实现规格 + 启动命令 |
