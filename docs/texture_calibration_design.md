# 纹理校准设计思想

## 背景

产品渲染 SaaS 中，表面处理（finish）由两个独立维度组成：
- **颜色**：由 RAL 色库 + base_color 控制
- **纹理**：由 bump、noise、roughness 等参数控制的表面质感

颜色和纹理必须解耦管理，分别校准。

## 设计原则

### 1. 纹理独立于颜色

纹理描述的是"表面质感"——粗糙度、凹凸、涂层纹路——与颜色无关。
- 纹理配置（`texture_profiles/*.json`）与 finish 配置（`finishes/*.json`）分开存储
- finish 通过 `texture_profile` 字段引用纹理
- 纹理预览用白底渲染（去颜色干扰），聚焦纹理本身

### 2. 两阶段校准

纹理校准分两个阶段，速度和精度递进：

```
Phase 1: 特征探索（快速，无需 API）
  - 用 LBP/GLCM/FFT/Sobel 提取纹理特征向量
  - Optuna TPE 优化 bakecoat 参数
  - 纯本地计算，每 trial ~10s
  - 目标：找到参数空间的粗略最优区域

Phase 2: VLM 精调（可选，需 API Key）
  - Phase 1 top-3 候选交给 VLM 评估
  - VLM 直接比较"看起来像不像"（人眼标准）
  - 比手工特征更准，但需要 API 调用
```

### 3. 纹理类型分级

不同纹理需要不同的程序化节点组合：

| 纹理类型 | 适用节点 | 示例 |
|---------|---------|------|
| 随机噪波 | Noise Texture | 砂纹、平面、超耐候 |
| 细胞纹理 | Voronoi Texture | 爆花（burst pattern） |
| 方向纹理 | Wave Texture + Anisotropic | 扫金漆拉丝 |
| 复合纹理 | 多层 Noise + Mix | 微晶陶瓷 |

当前实现使用 Noise Texture + Math(Add) + Bump 作为通用基线。特定类型需要扩展 `_full_material_render` 的节点树。

### 4. 配置分层架构

```
texture_profiles/<id>.json      ← 纹理参数（独立管理）
    ↑ 引用
finishes/<id>.json              ← PBR 参数 + 纹理引用
    ↑ 组合
catalog_colors.json             ← RAL 色库（颜色独立维度）
```

渲染管线自动合并：`resolve_texture_profile_bakecoat()` 读取 texture_profile 引用的 JSON，
合并到 finish 的 `bakecoat_procedural` 中，然后传递给 Blender 材质系统。

### 5. 传统校准管线关系

```
material_calibrate.py（已有）
  --mode material: 球体场景 + CIEDE2000 → 校准 PBR 参数（roughness/metallic/specular）
  
texture_calibrate.py（新增）
  --mode texture: 平板场景 + 纹理特征 → 校准 bakecoat 参数（bump/noise）
  
两者独立运行，互不依赖，最终合并到同一个 finish JSON。
```

### 6. 环境要求

- **必须使用 Docker**（`docker-compose.dev.yml`）
  - 数据库 data volume 持久化，杜绝数据丢失
  - 源码挂载 + `--reload`，开发效率不受影响
- **宿主机 Blender TCP**（port 19876）不变
  - Blender 在 GUI/headless 模式下运行效率更高
  - Docker 内 blenderworker 通过 `host.docker.internal:19876` 连接
