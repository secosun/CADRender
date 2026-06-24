# outdoor_sand 纹理校准待办

> 状态快照：2026-06-21  
> Run7 已完成 3 轮 VLM 闭环；**feature 最高轮 Round 2** 已写入 preset；验收渲染已通过。

---

## 当前状态（Run7）

| 轮次 | feature 分 | VLM 分 | 备注 |
|------|-----------|--------|------|
| Round 1 | 0.3656 | — | |
| **Round 2** | **0.3667** | — | **feature 最高，已写入 preset** |
| Round 3 | 0.3649 | 0.28 | pipeline 最终选中（VLM best） |

**Round 2 关键参数**：`micro_scale≈295`，`bump≈0.094`，`rough_mix≈0.726`

**验收产物**：
- `calibrate_out/acceptance_outdoor_sand/shader_ball.png`
- `calibrate_out/texture_outdoor_sand/compare_triple.png`
- `calibrate_out/texture_outdoor_sand/beauty_best.png`

---

## 待办清单

| # | 状态 | 任务 | 验收 / 备注 |
|---|------|------|-------------|
| 1 | ✅ 完成 | **验收 `compare_triple` + 金属球** | `acceptance_finish.py` 已通过 |
| 2 | ✅ 完成 | **VLM 闭环 3 轮** | `--texture-vlm-loop`，产物 `texture_vlm_loop.json` |
| 3 | ✅ 完成 | **写 preset（feature 最高轮）** | `write_feature_best_round.py outdoor_sand` → Round 2 |
| 4 | ⬜ 待做 | **产品 `render.py` 目检** | _guardrial.obj 等生产渲染 |
| 5 | ✅ 完成 | **文档补验收标准** | beauty/proxy 分离、Live Review 2×2、验收脚本 |
| 6 | ✅ 已实现 | **VLM 自主闭环** | `--texture-vlm-loop`；见 `texture_vlm_loop.py` |

---

## 阶段一：纹理校准跑对（必做）

### 看什么图

| 用途 | 路径 | 标准 |
|------|------|------|
| 纹理拟合（主依据） | `calibrate_out/texture_outdoor_sand/compare_triple.png` 中栏 | 团簇橘皮，接近左栏参考 |
| 频率排查 | 同图右栏 roughness 伪彩 | 中低频团块，非紫黄细点 |
| 外观预览 | `beauty_best.png`、`compare_beauty_pbr.png` | 掠射光下可见砂面 |
| Live Review | 桌面 2×2：Beauty \| Proxy × 上一张 \| 当前 | 实时对比 trial 进展 |

勿用 beauty 高通或旧版 `(unit-0.5)×42` 后处理图作 **Optuna 评分**；beauty 仅作审查。

### 命令

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --texture-trials 24 `
  --live-review

# VLM 自主闭环（推荐 GLCM 长期不达标时）
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --texture-trials 12 `
  --texture-vlm-loop `
  --texture-vlm-max-rounds 3 `
  --live-review

# 定稿验收
python scripts/acceptance_finish.py --finish-id outdoor_sand
python scripts/write_feature_best_round.py outdoor_sand
```

### 通过门槛（诚实评分）

- 总分 **≥ 0.55** 且 trial 间有上升趋势
- **GLCM**：render `glcm_contrast` ≥ ref 的 **50%**（ref≈0.74 → render **> 0.35**）
- **Sobel**：render `sobel_mean` 接近 ref（≈3–6），避免 60+ 的高频碎点

### 未达标时的旋钮（按顺序）

1. `micro_scale` 上界 → **450**，`fine_scale` → **1200**
2. 评分中 GLCM 权重再提高
3. `fine_detail` 上限 **9**；`rough_mix` 略提（0.5–0.7）
4. 隔离诊断：`python scripts/test/diag_snowflake_isolate.py --finish-id outdoor_sand`

---

## 阶段二：finish 串联（纹理 PASS 后）

```powershell
python scripts/calibrate.py --scope finish `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --live-review

python scripts/render.py --model assets/guardrial.obj --category aluminum_6063
```

- 球体：仅 PBR / 拉丝（MaterialModule）
- 平板：仅砂纹（TextureModule）
- 勿用球体图评砂纹
- 预览用 `preview.py`（默认生产模式）；`--calibration` 会剥砂纹，仅材质搜索时用

---

## 阶段三：文档与 UI

- Admin `/admin/calibration` 纹理 Tab 展示 `proxy_texture`、`compare_triple`
- 与 CLI Live Review 中栏逻辑一致
- Live Review 桌面窗口：Beauty \| Proxy 双栏 + 上一张/当前对比

---

## 成功标准（对外）

- 中栏 proxy 与蚁力参考团簇尺度、密度肉眼接近
- 右栏伪彩为中低频，非 salt-pepper
- beauty PBR 掠射光下可见砂面
- preset 写入 `finishes/outdoor_sand.json` + `texture_profiles/outdoor_sand.json`
- 生产 render 产品图户外砂纹可接受

---

## 相关文档

- [texture_calibration_design.md](./texture_calibration_design.md)
- [material_calibration_guide.md](./material_calibration_guide.md)
- [calibration_pipeline_design.md](./calibration_pipeline_design.md)
- 调研对照：《Blender照片转程序化纹理技术调研报告.docx》（工程落地 = Optuna + 参考图监督，非可微渲染）
