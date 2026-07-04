# 户外砂纹 / 粉末喷涂材质语义（专家参考）

> **样件**：蚁力色卡 `01-户外砂纹系列/11.jpg` · **琉璃灰金 特殊粉末**  
> **finish_id**：`outdoor_sand` · 与 G1 参考 crop `outdoor_sand_07.png` 同系列

---

## 1. 材质本质（与阳极/电泳的区别）

| 项 | 说明 |
|----|------|
| 基底 | 铝合金挤压型材 |
| 工艺 | 静电粉末喷涂 → 高温固化 **厚有机涂层** |
| 质感 | **塑料/涂层感**，金属感极弱；非裸露金属、非喷砂铝基材 |
| 纹理来源 | 粉末熔融固化后的 **微观表面起伏**，非拉丝/喷砂基材纹 |

---

## 2. 纹理与颜色（VLM / 人眼验收标准）

| 维度 | 合格特征 | 常见失败 |
|------|----------|----------|
| 颗粒 | 极细、高度均匀；肉眼近平整，掠射角才见起伏 | 块状、橙皮、Voronoi 斑、麻点 |
| 对比 | 局部对比 **极低** | 坑洼、豹纹 roughness、 harsh 微对比 |
| 凹凸 | 有效 bump **≤0.03**，仅微质感 | 立体颗粒、明显 pebble |
| 颜色 | 深炭黑 + 极弱冷灰；非纯黑 | 纯死黑或偏亮灰 |
| 高光 | 宽而柔的亮带，边缘平缓；极淡暖调细闪（琉璃灰金） | 锐利镜面、金属拉丝感 |

---

## 3. PBR 参数参考（球体 / preset 方向）

专家建议（整体 BSDF，非仅纹理层）：

| 参数 | 参考 | 说明 |
|------|------|------|
| Base Color | RGB≈(25,25,27) / #19191B | 深炭黑，弱冷灰 |
| Metallic | **0.05–0.10** | 涂层为主，勿拉高金属度 |
| Roughness | **0.65–0.75** | 半哑光砂感核心 |
| Coat | 0.10–0.15 | 致密表层 |
| Coat Roughness | **~0.8** | 清漆层也带砂感，避免锐利高光 |

当前 `outdoor_sand.json` 生产 preset 为 **金属基材 + 漆层 coat 栈**（metallic=1 为铝底），纹理校准 panel 用 neutral/coating 分离路径——**纹理 Optuna 只调 M_Bakecoat**，metallic 由 MaterialModule 锁定。

---

## 4. 纹理提取 / 评分要点

1. **去光照优先**：参考 crop 应取侧面均匀暗部；弧面高光带不参与纹理对齐  
2. **Roughness 通道**：整体 0.6–0.8，颗粒明暗差宜小（对应 v28 `rough_ramp 0.57–0.73`）  
3. **Normal/Bump**：极弱；与 v28 `bump_strength≈0.032` 一致  
4. **避坑**：勿做成高金属细砂；质感来自 **涂层漫反射**，非金属 specular

---

## 5. 对 VLM / A-lite 的映射

| 专家描述 | 工程动作 |
|----------|----------|
| 细砂均匀 | A-lite flat/proxy scorer + `micro_scale` 偏高 |
| 低对比 | 降 `bump_strength` / `valley_bump_boost`；VLM issue `contrast_too_high` |
| 非金属涂层 | VLM issue `too_metallic_look`（flag；metallic 不在 texture 搜索内） |
| 柔和高光 | Beauty PBR 验收；`coat_roughness` 由球体校准 |
| 去光照 | `_detrend_beauty_for_scoring` + 参考 crop 选平区 |

VLM prompt 已更新：`texture_vlm_loop.py` · `_TEXTURE_VLM_G1_PROMPT`

---

## 6. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-26 | 基于 11.jpg 专家描述归档；对齐 G1 VLM 语义 |
