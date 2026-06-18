# 材质标定实操指南（MaterialCal v2）

> **定位**：本系统校准的是 **渲染外观 preset**（look-dev），使 catalog 出图风格稳定一致；
> 输出的 `roughness` 等数值是 **Blender Principled 旋钮**，不是实验室测得的 BRDF 参数。
>
> `calibrate.py --mode material`：生产对齐球体 + 两阶段采样（256→1024spp）+
> Optuna 搜索 + trial 不确定性报告 + 可选多模型迁移验证 + 条件写入 finish JSON。

---

## 快速路线图

```
已有 11 种 finish → 直接用，零配置
新材质 → 创 finishes JSON → 跑校准（建议带 --model 验证）→ 类目校准 → 生产渲染
```

已有材质：`powder_matte` / `powder_glossy` / `anodized_black` / `anodized_silver` /
`brushed_aluminum` / `stainless_brushed` / `champagne_gold` / `electrophoretic` /
`fluorocarbon` / `gray_silver_metallic` / `wood_transfer`

---

## 架构概览

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
  "principled": {
    "base_color": [0.5, 0.5, 0.5, 1.0],
    "roughness": 0.3,
    "metallic": 0.0,
    "specular_ior_level": 0.5,
    "coat_weight": 0.2,
    "coat_roughness": 0.3,
    "coat_ior": 1.5
  },
  "bakecoat_procedural": {
    "bump": { "strength": 0.02, "distance": 1.0 },
    "micro": { "scale": 720, "detail": 11, "roughness": 0.48 }
  }
}
```

**`base_color` 是唯一必须人工精确定义的参数**；`lighting_profile` 决定球体与生产使用同一套灯光。

| 材质类型 | gate_profile | lighting_profile |
|---------|-------------|-----------------|
| 深色哑光（黑/深灰喷粉） | `dark_matte` | `dark` |
| 中等色调（银灰/香槟/拉丝铝） | `mid_matte` | `mid` |
| 亮色（白/浅灰） | `bright` | `light` |
| 高反光金属 | `mid_matte` | `bright` |

---

## 第二步：运行校准

确保 **Blender TCP 已启动**：

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

# 推荐：完整闭环 + 多几何验证
python scripts/calibrate.py --mode material `
  --finish-id my_new_finish `
  --models assets/guardrial.obj,assets/简易款-BodyPad003.obj `
  --category aluminum_6063

# 单模型验证
python scripts/calibrate.py --mode material `
  --finish-id my_new_finish `
  --model assets/guardrial.obj `
  --category aluminum_6063

# 仅球体（更快，无迁移验证）
python scripts/calibrate.py --mode material --finish-id my_new_finish

# 快速迭代（跳过 1024spp 确认）
python scripts/calibrate.py --mode material --finish-id my_new_finish --skip-confirm
```

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

材质校准完成后，对该产品类目跑一次类目校准（不改材质）：

```powershell
python scripts/calibrate.py --mode category `
  --model assets/guardrial.obj `
  --category aluminum_6063
```

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
| 拉丝铝 | ~0.35 | 1.0 | ~0.5 | ~0.05 |
| 阳极氧化黑 | ~0.30 | 1.0 | ~0.5 | ~0.15 |

---

## 配色扩展

在 `blender_mcp_presets/catalog_colors.json` 中为 finish 增加配色（仅覆盖 `base_color`）。

---

## 从简单开始

1. 先用 `powder_matte` + 已有配色
2. 新 finish：**务必设对 `lighting_profile`**，与产品类目一致
3. 校准命令**尽量带 `--model`**，让系统自动做迁移验证
4. 验证 FAIL 时先看 `validation_report.json`，再决定是否 `--force-write`
