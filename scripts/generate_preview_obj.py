"""生成标准 OBJ 文件用于 3D 预览 — 正确面绕序，无缺失面。"""

import math
import os
import sys


def make_cube_obj() -> str:
    """Unit cube [-0.5, 0.5] with correct face winding."""
    lines = ["# Cube preview for CADRender", "o Cube"]

    # Vertices: x,y,z
    v = [
        (-0.5, -0.5, -0.5),  # 0 front-left-bottom
        ( 0.5, -0.5, -0.5),  # 1 front-right-bottom
        (-0.5,  0.5, -0.5),  # 2 front-left-top
        ( 0.5,  0.5, -0.5),  # 3 front-right-top
        (-0.5, -0.5,  0.5),  # 4 back-left-bottom
        ( 0.5, -0.5,  0.5),  # 5 back-right-bottom
        (-0.5,  0.5,  0.5),  # 6 back-left-top
        ( 0.5,  0.5,  0.5),  # 7 back-right-top
    ]
    for x, y, z in v:
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")

    # Normals
    for n in [(0,0,-1), (0,0,1), (-1,0,0), (1,0,0), (0,-1,0), (0,1,0)]:
        lines.append(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}")

    lines.append("vt 0 0")  # dummy UV

    # Faces: each with 2 triangles, CCW winding from outside
    # format: f v1/vt1/vn1 v2/vt1/vn1 v3/vt1/vn1
    # Face order: [tri1_v1, tri1_v2, tri1_v3, tri2_v1, tri2_v2, tri2_v3, normal_index]
    faces = [
        # Front (-Z)
        (0, 2, 3,  0, 3, 1,  1),
        # Back (+Z)
        (5, 7, 6,  5, 6, 4,  2),
        # Left (-X)
        (4, 6, 2,  4, 2, 0,  3),
        # Right (+X)
        (1, 3, 7,  1, 7, 5,  4),
        # Bottom (-Y)
        (4, 0, 1,  4, 1, 5,  5),
        # Top (+Y)
        (2, 6, 7,  2, 7, 3,  6),
    ]

    for a, b, c, d, e, f, ni in faces:
        lines.append(f"f {a+1}/1/{ni} {b+1}/1/{ni} {c+1}/1/{ni}")
        lines.append(f"f {d+1}/1/{ni} {e+1}/1/{ni} {f+1}/1/{ni}")

    return "\n".join(lines) + "\n"


def make_cylinder_obj(segments: int = 48) -> str:
    """Unit cylinder (radius 0.5, height 1.0, centered at origin)."""
    lines = ["# Cylinder preview for CADRender", "o Cylinder"]
    r, h = 0.5, 0.5

    # Vertices
    # 0: bottom center, 1: top center
    lines.append(f"v 0 {-h:.6f} 0")
    lines.append(f"v 0 {h:.6f} 0")
    # 2..2+segments-1: bottom ring
    for i in range(segments):
        a = 2 * math.pi * i / segments
        lines.append(f"v {r*math.cos(a):.6f} {-h:.6f} {r*math.sin(a):.6f}")
    # 2+segments..2+2*segments-1: top ring
    for i in range(segments):
        a = 2 * math.pi * i / segments
        lines.append(f"v {r*math.cos(a):.6f} {h:.6f} {r*math.sin(a):.6f}")

    # Normals
    lines.append("vn 0 -1 0")   # 1: bottom
    lines.append("vn 0 1 0")    # 2: top
    for i in range(segments):   # 3..3+segments-1: side
        a = 2 * math.pi * i / segments
        lines.append(f"vn {math.cos(a):.6f} 0 {math.sin(a):.6f}")

    lines.append("vt 0 0")  # dummy UV

    br = 2               # bottom ring start
    tr = 2 + segments    # top ring start

    # Bottom cap (fan from center 0, normal 1)
    for i in range(segments):
        i0 = br + i
        i1 = br + (i + 1) % segments
        lines.append(f"f 1/1/1 {i1+1}/1/1 {i0+1}/1/1")

    # Top cap (fan from center 1, normal 2)
    for i in range(segments):
        i0 = tr + i
        i1 = tr + (i + 1) % segments
        lines.append(f"f 2/1/2 {i0+1}/1/2 {i1+1}/1/2")

    # Side (quad strip, normal 3+i)
    for i in range(segments):
        b0 = br + i
        b1 = br + (i + 1) % segments
        t0 = tr + i
        t1 = tr + (i + 1) % segments
        ni = 3 + i
        # Two triangles per quad, CCW from outside
        lines.append(f"f {b0+1}/1/{ni} {b1+1}/1/{ni} {t1+1}/1/{ni}")
        lines.append(f"f {b0+1}/1/{ni} {t1+1}/1/{ni} {t0+1}/1/{ni}")

    return "\n".join(lines) + "\n"


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python generate_preview_obj.py <cube|cylinder> <output_path>")
        sys.exit(1)

    shape = sys.argv[1]
    output = sys.argv[2]

    if shape == 'cube':
        data = make_cube_obj()
    elif shape == 'cylinder':
        data = make_cylinder_obj()
    else:
        print(f"Unknown shape: {shape}")
        sys.exit(1)

    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    with open(output, 'w') as f:
        f.write(data)
    print(f"Generated {shape} OBJ → {output} ({len(data)} bytes)")
