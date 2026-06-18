# 美术资产待办清单

> CADRender 渲染系统：模型由开发自建，本文档管理其余美术资产的生产计划。

---

## 一、FreeCAD 参数化模板

建模板流程：草图 → 定义 Spreadsheet 参数（长/宽/厚/孔径等）→ 导出 `.FCStd` → 注册到 `blenderserver`。

### P0 — 核心模板（先做）

| # | 模板名称 | 类目 | 参数示例 | 预估工时 |
|---|---------|------|---------|---------|
| 1 | 直扶手（straight_handrail） | 铝型材/栏杆 | 长度 L、截面宽 W、壁厚 T | 4-6h |
| 2 | 栏杆立柱（railing_post） | 铝型材/栏杆 | 高度 H、截面 W×D、底座类型 | 4-6h |
| 3 | 平开门框（door_frame） | 门窗框 | 门洞宽 W、高 H、型材截面 | 6-8h |
| 4 | 推拉门框（sliding_door_frame） | 门窗框 | 门洞宽 W、高 H、轨道数 N | 6-8h |
| 5 | 窗框（window_frame） | 门窗框 | 窗洞宽 W、高 H、型材截面 | 6-8h |
| 6 | 拉手（handle） | 五金件 | 长度 L、安装孔距 P、截面 | 4-6h |
| 7 | 合页（hinge） | 五金件 | 长 L、宽 W、片数 N | 3-4h |
| 8 | 锁面板（lock_plate） | 五金件 | 长 L、宽 W、孔位 | 3-4h |

### P1 — 扩展模板（按需）

| # | 模板名称 | 类目 | 预估工时 |
|---|---------|------|---------|
| 9 | 铝板（aluminum_plate） | 板材 | 2-3h |
| 10 | 冲孔板（perforated_plate） | 板材 | 3-4h |
| 11 | 方管（square_tube） | 管材 | 2-3h |
| 12 | 圆管（round_tube） | 管材 | 2-3h |
| 13 | 角码（angle_bracket） | 连接件 | 2-3h |
| 14 | 装饰条（trim_strip） | 装饰件 | 2-3h |

**总计 P0：约 5-7 天  |  P0+P1：约 8-10 天**

---

## 二、配色扩展

当前 `catalog_colors.json` 仅 3 色。按材质类型扩展色卡。

### powder_matte（哑光喷粉）— 扩展 6 色

| 颜色 ID | label_zh | base_color (RGB 0-1) | 优先级 |
|---------|----------|---------------------|--------|
| powder_off_white | 哑光白喷粉 | 0.82, 0.82, 0.805 | ✅ 已有 |
| powder_black | 深黑喷粉 | 0.07, 0.07, 0.07 | ✅ 已有 |
| powder_dark_gray | 深灰喷粉 | 0.045, 0.045, 0.048 | ✅ 已有 |
| powder_coffee | 咖啡棕 | 待定 | P0 |
| powder_navy | 深蓝 | 待定 | P0 |
| powder_dark_green | 墨绿 | 待定 | P1 |
| powder_brick_red | 砖红 | 待定 | P1 |
| powder_warm_gray | 暖灰 | 待定 | P1 |

### anodized 系列（阳极氧化）— 扩展 4 色

| 颜色 ID | label_zh | 优先级 |
|---------|----------|--------|
| anodized_black | 阳极氧化黑 | ✅ 已有 |
| anodized_silver | 阳极氧化银 | ✅ 已有 |
| anodized_gun | 枪色 | P0 |
| anodized_titanium | 钛灰 | P1 |
| anodized_rose_gold | 玫瑰金 | P2 |

### 其他材质配色

| 材质 | 建议颜色 | 优先级 |
|------|---------|--------|
| brushed_aluminum 拉丝铝 | 银色 ✅、枪色 P1 | P1 |
| powder_glossy 亮光喷粉 | 亮白、亮黑、金色、银灰 | P1 |
| wood_transfer 木纹转印 | 胡桃木、橡木、樱桃木、柚木 | P1 |
| stainless_brushed 拉丝不锈钢 | 本色 ✅、金色 P2 | P2 |

**配色扩展流程：**
1. 在 `catalog_colors.json` 中新增 color ID + base_color + label_zh
2. 运行 `scripts/render.py` 渲染验证
3. 注册到 `blenderserver` 的 finishes API

---

## 三、分类 → 材质映射

为每个产品分类指定默认材质和可选颜色。在 `product_presets.json` 的 `categories.<cat>` 中配置。

| 分类 | 默认 finish | 可选颜色 | 状态 |
|------|-----------|---------|------|
| generic | powder_matte | 所有 | ✅ 已有 |
| aluminum_6063 | powder_matte | 黑/深灰/白 + 新色 | ✅ 已有 |
| aluminum_gunmetal_railing | anodized_black | 枪色/黑 | ✅ 已有 |
| door_window_railing | electrophoretic | 黑/深灰/咖啡 | ⚠️ 需完善配色 |
| coating_black_product | powder_matte_black | 黑 | ✅ 已有 |
| coating_orange_yellow_powder | powder_glossy | 橙/黄 | ✅ 已有 |
| coating_gray_metal_plate | gray_silver_metallic | 银灰 | ✅ 已有 |
| coating_automotive_texture | powder_glossy | 黑/白/灰 | ⚠️ 需完善 |
| polyhaven_anti_slip_concrete | powder_matte | 灰 | ⚠️ 需完善 |

**映射配置需要注意：**
- 每个分类的 `studio_lighting_mult`、`framing.margin`、`mesh_processing` 需要按产品形状微调
- 深色材质用 `dark` lighting_profile，浅色用 `light`

---

## 四、品类灯光微调（按需）

当前灯光系统有 3 套亮度自适应方案（dark / mid / light），覆盖了大多数场景。

如果需要更专业的品类特定灯光，在 `lighting_profiles/` 中新增：

| 品类 | 建议灯光风格 | 优先级 | 备注 |
|------|------------|--------|------|
| 型材/栏杆 | 长条柔光箱 + 轮廓光 | P1 | 强调线性造型 |
| 门窗框 | 宽柔光箱 + 背景光 | P1 | 展示整体结构 |
| 五金件 | 小面积硬光 + 反射板 | P1 | 凸显金属质感 |

---

## 五、参考图金标（VLM 评分基准）

现在已经有 5 张参考图（低质量 5.3 分 vs 高质量 8.9-9.05 分）。按新类目扩展：

| 类目 | 需要金标参考图 | 优先级 | 用途 |
|------|--------------|--------|------|
| 型材/栏杆 | 2-3 张行业竞品图 | P0 | 评分锚定 |
| 门窗框 | 2-3 张 | P1 | 评分锚定 |
| 五金件 | 2-3 张 | P1 | 评分锚定 |

---

## 工作量汇总

| 类别 | 项数 | 预估工时 | 依赖 |
|------|------|---------|------|
| FreeCAD 模板（P0） | 8 个 | 5-7 天 | 无 |
| FreeCAD 模板（P1） | 6 个 | 3-5 天 | P0 完成 |
| 配色扩展 | 15-20 色 | 1-2 天 | 模板完成 |
| 分类映射配置 | 5-6 个分类微调 | 0.5 天 | 模板 + 配色 |
| 灯光微调 | 3 个品类 | 1-2 天 | 模板测试 |
| 参考图金标 | 6-9 张 | 1 天 | 无 |

**总计初期投入：约 2-3 周（一个人兼职）**

---

## 操作参考

```powershell
# 1. 上传 FreeCAD 模板到系统
# (通过 blenderserver API 或前端)

# 2. 验证渲染效果
python blenderworker/scripts/render.py --model <path/to/obj> --category <category>

# 3. 新增 finish 材质（如需）
# 参考 docs/add_finish.md

# 4. 注册新分类到系统
# 编辑 blenderserver/core/intent_parser.py 中的类别列表
# 编辑 blenderworker/src/planning/intent_mvp.py 中的 MVP_PRODUCT_CATEGORIES
```
