# 材质标定实操指南

> 系统已内置 `calibrate.py --mode material` 自动材质校准，
> 通过贝叶斯优化探索 roughness/metallic/specular 参数空间，
> 自动评分并写入最佳参数到 JSON。

---

## 快速路线图

```
如果产品表面处理在已有 11 种材质中 → 直接用，零配置
如果不在 → 两步配新材质（创 JSON → 跑校准）
```

已有材质：`powder_matte` / `powder_glossy` / `anodized_black` / `anodized_silver` / `brushed_aluminum` / `stainless_brushed` / `champagne_gold` / `electrophoretic` / `fluorocarbon` / `gray_silver_metallic` / `wood_transfer`

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
  }
}
```

**`base_color` 是你要给的唯一关键参数**，其余 principled 值写个大概就行，校准工具会覆盖。

**`gate_profile` / `lighting_profile` 选择参考：**

| 材质类型 | gate_profile | lighting_profile |
|---------|-------------|-----------------|
| 深色哑光（黑/深灰喷粉） | `dark_matte` | `dark` |
| 中等色调（银灰/香槟/拉丝铝） | `mid_matte` | `mid` |
| 亮色（白/浅灰/混凝土） | `bright` | `light` |
| 高反光金属（镜面/抛光） | `mid_matte` | `bright` |

---

## 第二步：运行贝叶斯自动校准

确保 **Blender TCP 服务已启动**，然后：

```powershell
cd blenderworker
python scripts/calibrate.py --mode material --finish-id my_new_finish
```

### 校准过程

系统自动执行以下流程（约 5-10 分钟）：

| 步骤 | 内容 |
|------|------|
| 1. 创建标准球体场景 | 倒角球体 + 三点布光 + HDRI + AgX，1024x1024，256spp |
| 2. 贝叶斯搜索 | 8 轮随机初始化 + 18 轮 GP-EI 引导 = **~26 次渲染** |
| 3. 自动评分 | 每轮渲染后计算边缘能量 + 色彩保真度综合得分 |
| 4. 选优 | 算法自动选出得分最高的 roughness/metallic/specular 组合 |
| 5. 输出结果 | 各变体 PNG + `00_summary_grid.png` 汇总图 |
| 6. 写入 JSON | 自动将最佳参数写入 `finishes/<finish_id>.json` |

### 你需要做的

1. 跑完脚本后，打开 `calibrate_out/material_<finish_id>/00_summary_grid.png`
2. 看一眼所有变体的渲染效果（每张标注了 R/M/S 值和 score）
3. 如果算法选的效果 OK → 不用管，已经写入了
4. 如果算法选的不对 → 手动改 `finishes/<finish_id>.json` 里的值

### 参数搜索范围

| 参数 | 搜索范围 | 粒度 |
|------|---------|------|
| roughness | 0.10 - 0.85 | 连续贝叶斯 |
| metallic | 0.00 - 1.00 | 0.2 步进网格 |
| specular_ior_level | 0.00 - 1.00 | 0.1/0.25 步进 |

---

## 材质参数速查

### Principled BSDF 参数含义

| 参数 | 范围 | 0 的效果 | 1 的效果 | 常用场景 |
|------|------|---------|---------|---------|
| **roughness** | 0-1 | 镜面反射 | 完全哑光 | 喷粉 0.4-0.6, 金属 0.1-0.3 |
| **metallic** | 0-1 | 非金属（塑料/漆面） | 纯金属 | 喷粉 0, 铝材 0.8-1.0 |
| **specular_ior_level** | 0-1 | 无高光 | 强高光 | 默认 0.5, 漆面 0.7-0.9 |
| **coat_weight** | 0-1 | 无清漆层 | 厚清漆 | 汽车漆 0.3, 喷粉 0.1-0.2 |
| **anisotropic** | 0-1 | 各项同性 | 强拉丝 | 拉丝铝 0.6, 不锈钢 0.8 |

### 核心原则

```
roughness 越低 → 反光越强 → 看起来越"亮"
metallic 越高 → 反射颜色越接近 base_color
coating 越高 → 表面越像有一层清漆
base_color 越深 → 灯光自动补偿（系统自动处理）
```

### 常见材质配方参考

| 材质 | roughness | metallic | specular | coat_weight | anisotropic |
|------|-----------|----------|----------|-------------|-------------|
| 哑光黑喷粉 | ~0.50 | 0.0 | ~0.3 | ~0.20 | - |
| 亮光白漆 | ~0.15 | 0.0 | ~0.7 | ~0.35 | - |
| 拉丝铝 | ~0.35 | 1.0 | ~0.5 | ~0.05 | ~0.6 |
| 不锈钢拉丝 | ~0.30 | 1.0 | ~0.5 | ~0.05 | ~0.8 |
| 阳极氧化黑 | ~0.30 | 1.0 | ~0.5 | ~0.15 | - |
| 镜面不锈钢 | ~0.05 | 1.0 | ~0.7 | 0.0 | - |
| 氟碳漆（灰） | ~0.40 | 0.0 | ~0.5 | ~0.15 | - |
| 香槟金 | ~0.40 | 0.0 | ~0.5 | ~0.20 | - |
| 电泳黑 | ~0.60 | 0.0 | ~0.3 | ~0.10 | - |

这些只是参考起点，校准工具会自动找到最适合的值。

---

## 配色扩展

材质调好之后，在 `blender_mcp_presets/catalog_colors.json` 中加配色：

```json
{
  "my_color_id": {
    "label_zh": "颜色名",
    "principled": {
      "base_color": [0.2, 0.3, 0.5, 1.0]
    }
  }
}
```

每个 finish 配 3-5 个常用色即可。注意 base_color 是线性 RGB，通常比 sRGB 值看起来暗。

---

## 从简单开始

1. **先用现成的**：`powder_matte` + 配色就覆盖 80% 的型材/门窗产品
2. **只做当前产品需要的材质**：接什么产品，调什么材质
3. **跑校准就行**：不用猜参数，`calibrate.py` 自动跑 26 轮渲染，挑最好的
