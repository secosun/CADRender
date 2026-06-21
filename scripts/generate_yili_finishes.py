"""Generate new finishes based on Yili powder coating series."""
import json, os

FINISHES_DIR = 'D:/咸阳/框架评审/CADRender/blenderworker/blender_mcp_presets/finishes'
MATERIALS_DIR = 'D:/咸阳/框架评审/CADRender/blenderworker/blender_mcp_presets/materials/finishes'

NEW_FINISHES = [
    {
        "id": "outdoor_sand",
        "label_zh": "户外砂纹",
        "gate_profile": "dark_matte",
        "lighting_profile": "dark",
        "view_exposure": -0.4,
        "hdri_strength": 0.35,
        "world_strength": 0.15,
        "calibration": {"lock_metallic": True},
        "principled": {
            "base_color": [0.25, 0.22, 0.18, 1.0],
            "roughness": 0.75,
            "metallic": 0.0,
            "specular_ior_level": 0.3,
            "coat_weight": 0.05,
            "coat_roughness": 0.5,
            "coat_ior": 1.5,
        },
        "bakecoat_procedural": {
            "micro": {"scale": 300.0, "detail": 15.0, "roughness": 0.6},
            "fine": {"scale": 1500.0, "detail": 14.0, "roughness": 0.5},
            "bump": {"strength": 0.08, "distance": 1.0},
            "rough_ramp": {"to_min": 0.7, "to_max": 0.95},
            "rough_mix_factor": 0.7,
        },
    },
    {
        "id": "microcrystalline",
        "label_zh": "微晶陶瓷",
        "gate_profile": "mid_glossy",
        "lighting_profile": "mid",
        "view_exposure": -0.2,
        "hdri_strength": 0.45,
        "world_strength": 0.2,
        "calibration": {"lock_metallic": True},
        "principled": {
            "base_color": [0.75, 0.73, 0.70, 1.0],
            "roughness": 0.35,
            "metallic": 0.0,
            "specular_ior_level": 0.6,
            "coat_weight": 0.3,
            "coat_roughness": 0.15,
            "coat_ior": 1.6,
        },
        "bakecoat_procedural": {
            "micro": {"scale": 500.0, "detail": 8.0, "roughness": 0.4},
            "fine": {"scale": 2000.0, "detail": 10.0, "roughness": 0.3},
            "bump": {"strength": 0.015, "distance": 1.0},
            "rough_ramp": {"to_min": 0.85, "to_max": 0.98},
            "rough_mix_factor": 0.3,
        },
    },
    {
        "id": "burst_pattern",
        "label_zh": "户外爆花",
        "gate_profile": "mid_matte",
        "lighting_profile": "mid",
        "view_exposure": -0.3,
        "hdri_strength": 0.4,
        "world_strength": 0.2,
        "calibration": {"lock_metallic": True},
        "principled": {
            "base_color": [0.18, 0.15, 0.12, 1.0],
            "roughness": 0.65,
            "metallic": 0.0,
            "specular_ior_level": 0.4,
            "coat_weight": 0.15,
            "coat_roughness": 0.35,
            "coat_ior": 1.5,
        },
        "bakecoat_procedural": {
            "micro": {"scale": 200.0, "detail": 12.0, "roughness": 0.55},
            "fine": {"scale": 800.0, "detail": 13.0, "roughness": 0.45},
            "bump": {"strength": 0.12, "distance": 1.0},
            "rough_ramp": {"to_min": 0.6, "to_max": 0.9},
            "rough_mix_factor": 0.65,
        },
    },
    {
        "id": "gold_sweeping",
        "label_zh": "户外扫金漆",
        "gate_profile": "mid_glossy",
        "lighting_profile": "mid",
        "view_exposure": -0.2,
        "hdri_strength": 0.5,
        "world_strength": 0.25,
        "principled": {
            "base_color": [0.72, 0.55, 0.15, 1.0],
            "roughness": 0.3,
            "metallic": 0.8,
            "specular_ior_level": 0.7,
            "anisotropic": 0.6,
            "anisotropic_rotation": 0.0,
            "coat_weight": 0.1,
            "coat_roughness": 0.2,
            "coat_ior": 1.5,
        },
        "bakecoat_procedural": {
            "bump": {"strength": 0.015, "distance": 1.0},
            "rough_mix_factor": 0.2,
        },
    },
]

def main():
    for finish in NEW_FINISHES:
        fid = finish["id"]
        # Write finish JSON
        finish_path = os.path.join(FINISHES_DIR, f"{fid}.json")
        finish_data = {
            "id": fid,
            "label_zh": finish["label_zh"],
            "gate_profile": finish["gate_profile"],
            "lighting_profile": finish["lighting_profile"],
            "material_folder": f"materials/finishes/{fid}",
            "view_exposure": finish["view_exposure"],
            "hdri_strength": finish["hdri_strength"],
            "world_strength": finish["world_strength"],
        }
        if finish.get("calibration"):
            finish_data["calibration"] = finish["calibration"]
        finish_data["principled"] = finish["principled"]
        finish_data["bakecoat_procedural"] = finish["bakecoat_procedural"]

        with open(finish_path, "w", encoding="utf-8") as f:
            json.dump(finish_data, f, ensure_ascii=False, indent=2)
        print(f"Created finish: {fid}")

        # Write material.json
        mat_dir = os.path.join(MATERIALS_DIR, fid)
        os.makedirs(mat_dir, exist_ok=True)
        material = {"kind": "procedural_pbr", "builder": "bakecoat_principled"}
        with open(os.path.join(mat_dir, "material.json"), "w", encoding="utf-8") as f:
            json.dump(material, f, ensure_ascii=False, indent=2)
        print(f"  -> material dir: {mat_dir}")

    print(f"\nDone. Created {len(NEW_FINISHES)} new finishes.")

if __name__ == "__main__":
    main()
