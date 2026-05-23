import json, sys
try:
    with open("D:/咸阳/框架评审/CADRender/blenderworker/blender_mcp_presets/product_presets.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    cats = data.get("categories", {})
    print(f"JSON OK: {len(cats)} categories")
    print(f"Render defaults final samples: {data['render_defaults']['final']['samples']}")
    print(f"Denoising enabled: {data['render_defaults']['final']['cycles'].get('use_denoising')}")
except json.JSONDecodeError as e:
    print(f"JSON Error at line {e.lineno} col {e.colno}: {e.msg}")
    # Print surrounding context
    with open("D:/咸阳/框架评审/CADRender/blenderworker/blender_mcp_presets/product_presets.json", "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i in range(max(0, e.lineno-5), min(len(lines), e.lineno+2)):
        marker = ">>>" if i+1 == e.lineno else "   "
        print(f"{marker} {i+1}: {lines[i].rstrip()}")
except Exception as e:
    print(f"Error: {e}")
