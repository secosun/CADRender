# 纹理贴图提取使用指南

> **2026-07 新增**  
> 从蚁力色卡 crop 提取干净纹理贴图，作为程序化 M_Bakecoat 拟合的评分目标，提升校准信噪比。  
> 设计文档见 [texture_calibration_design.md](./texture_calibration_design.md#10-%E7%BA%B9%E7%90%86%E8%B4%B4%E5%9B%BE%E6%8F%90%E5%8F%96%E7%AE%A1%E7%BA%BF-usetexturemap)。

---

## 快速入门

```powershell
cd blenderworker
$env:PYTHONPATH = "src"

# 一步提取纹理贴图（对 outdoor_sand）
python scripts/extract_texture_map.py --finish-id outdoor_sand

# 提取成功后，用贴图作为参考重跑校准
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --use-texture-map `
  --texture-trials 24 `
  --no-auto-write
```

---

## 完整工作流

### 第 1 步：确认蚁力 crop 存在

```powershell
ls ../outputs/yili_crops/outdoor_sand/
# 应看到类似: outdoor_sand_crop.png outdoor_sand_00.png ...
```

如果没有 crop，先运行裁剪脚本：

```powershell
python ../scripts/crop_yili_references.py --finish-id outdoor_sand
```

### 第 2 步：提取纹理贴图

```powershell
# 内置提取（免费，零额外依赖）
python scripts/extract_texture_map.py --finish-id outdoor_sand
```

输出（均在 `../outputs/yili_crops/outdoor_sand/`）：

| 文件 | 说明 |
|------|------|
| `outdoor_sand_texture_map.png` | **主贴图** — 去光照、去噪、无缝化，作为评分目标 |
| `outdoor_sand_texture_map_bump.png` | bump 代理图，供诊断对比 |
| `outdoor_sand_texture_map_qa.json` | 质量指标 |

提取日志示例：

```
INFO Texture map saved: outdoor_sand_texture_map.png
     (flatness=2.14 seam=0.032 hf_corr=0.68 qa_pass=True)
```

如果 `qa_pass=False`，建议改用外部工具（见下文）。

### 第 3 步：使用贴图校准

```powershell
python scripts/calibrate.py --scope texture `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --use-texture-map `
  --texture-trials 24 `
  --no-auto-write
```

`--use-texture-map` 的作用：

1. 自动在同目录找 `outdoor_sand_texture_map.png`
2. 如果找到，用贴图替代原始 crop 作为 Optuna 评分目标
3. 评分器走轻量预处理（`preprocess_texture_map`），跳过高通/去梯度步骤
4. 校准报告会标注 `texture_map=true`

### 第 4 步：审查

生成的审查图（`calibrate_out/texture_outdoor_sand/`）：

- `compare_triple.png` — 参考贴图 \| proxy \| 粗糙度伪彩
- `compare_beauty_pbr.png` — 参考 vs Beauty PBR
- `texture_calibration_report.json` — 含 `scoring_ref_source: "texture_map"`

### 第 5 步：定稿

```powershell
# 写入 preset
python scripts/write_feature_best_round.py outdoor_sand

# 金属球验收
python scripts/acceptance_finish.py --finish-id outdoor_sand

# 组合验收
python scripts/render.py --model assets/guardrial.obj --category aluminum_6063
```

---

## 使用外部工具（质量优先）

如果内置提取的 QA 未通过（`qa_pass=False`），或者需要更高精度的贴图，推荐以下工具链：

### DeepBump（免费 Blender 插件）

```powershell
# 1. 在 Blender 中用 DeepBump 打开 outdoor_sand_crop.png
# 2. 导出 Roughness map 为 outdoor_sand_deepbump_roughness.png
# 3. 导入到标准路径
python scripts/extract_texture_map.py --finish-id outdoor_sand `
  --external ../outputs/yili_crops/outdoor_sand/outdoor_sand_deepbump_roughness.png
```

### Substance 3D Sampler

```powershell
# 1. 在 Substance 中加载 crop 图
# 2. 生成 tileable 纹理，导出 PNG
# 3. 导入
python scripts/extract_texture_map.py --finish-id outdoor_sand `
  --external path/to/substance_export.png
```

外部模式会自动：
- 将外部贴图复制到 `<finish_id>_texture_map.png`
- 计算基础 QA（平坦度检查）
- **不做任何二次处理**（保证第三方质量不降级）

---

## QA 指标说明

提取时的 QA 门控：

| 指标 | 通过条件 | 超标含义 |
|------|---------|---------|
| `baseline_flatness_std` | < 5.0 | 去光照不干净 |
| `seam_intensity` | < 0.08 | 无缝化不充分，平铺可见接缝 |
| `hf_corr_raw_vs_map` | > 0.4 | 贴图丢失了原图纹理结构 |

如果 `qa_pass=false`：

1. 尝试使用更大或更中心的 crop（`--reference` 参数指向其他 crop 文件）
2. 或改用外部工具
3. 或直接不使用 `--use-texture-map`，fallback 到原始 crop 校准

---

## 配合归档重跑

```powershell
python scripts/run_texture_cal_round.py `
  --finish-id outdoor_sand `
  --reference ../outputs/yili_crops/outdoor_sand/outdoor_sand_crop.png `
  --use-texture-map `
  --archive-label pre_texture_map `
  --texture-trials 24 `
  --no-auto-write
```

---

## 与现有校准流程的关系

| 场景 | 用什么 |
|------|--------|
| 首次校准 / 快速验证 | 原始 crop（不加 `--use-texture-map`） |
| 精调定稿 / 接近天花板 | **贴图 + `--use-texture-map`** |
| 程序化确实拟合不了 | 直接 B 轨 Image Texture（原 crop 生成贴图后在材质中用） |

---

## 常见问题

**Q: 为什么提取的贴图是灰度图？**  
A: 纹理校准只关心表面起伏和粗糙度，不需要颜色信息。评分器基于 LBP/GLCM/FFT/Sobel 特征，灰度输入足够。

**Q: 提取出来的贴图可以直接用在生产材质中吗？**  
A: 可以——这就是双轨中 B 轨（Image Texture）的入口。`_texture_map.png` 可以直接作为 `build_texture_pbr_material` 的输入，走 M_PBR_Core。但目前 A 轨（程序化）+ 贴图评分仍是主线。
