"""为参数化模板生成预览 GLB 文件。

用法: python generate_preview_glb.py <template_type> <output_path>
  template_type: cube | cylinder

生成的 GLB 文件可用 @google/model-viewer 在浏览器中展示。
"""

import json
import os
import sys
import tempfile

# GLB binary format helper — writes a minimal mesh as GLB
# This creates a valid GLB with position + normal attributes

def _pack_uint32(n: int) -> bytes:
    return n.to_bytes(4, 'little')

def _pack_float32(n: float) -> bytes:
    import struct
    return struct.pack('<f', n)

def _pack_vec3(v) -> bytes:
    return _pack_float32(v[0]) + _pack_float32(v[1]) + _pack_float32(v[2])

def _make_cube_glb() -> bytes:
    """Generate a GLB file for a unit cube [-0.5, 0.5]."""
    # 8 vertices, 36 indices (12 triangles)
    verts = [
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5),
    ]
    normals = [
        (0, 0, -1), (0, 0, 1), (-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0),
    ]
    # Face indices (triangulated): 6 faces × 2 triangles × 3 indices
    faces = [
        0,1,2, 0,2,3,  # -Z
        4,6,5, 4,7,6,  # +Z
        0,4,5, 0,5,1,  # -X
        3,2,6, 3,6,7,  # +X
        0,3,7, 0,7,4,  # -Y
        1,5,6, 1,6,2,  # +Y
    ]
    # Per-face normals
    face_normals = [0]*6 + [1]*6 + [2]*6 + [3]*6 + [4]*6 + [5]*6

    return _build_glb(verts, normals, faces, face_normals)


def _make_cylinder_glb(segments: int = 32) -> bytes:
    """Generate a GLB file for a unit cylinder (radius 0.5, height 1.0)."""
    verts = []
    normals = []
    indices = []
    face_normals_idx = []

    r = 0.5
    h = 0.5

    # Bottom center
    verts.append((0, -h, 0))
    normals.append((0, -1, 0))
    bottom_center = 0

    # Bottom ring
    for i in range(segments):
        a = 2 * 3.14159 * i / segments
        verts.append((r * __import__('math').cos(a), -h, r * __import__('math').sin(a)))
        normals.append((0, -1, 0))

    # Top center
    top_center = len(verts)
    verts.append((0, h, 0))
    normals.append((0, 1, 0))

    # Top ring
    top_start = len(verts)
    for i in range(segments):
        a = 2 * 3.14159 * i / segments
        verts.append((r * __import__('math').cos(a), h, r * __import__('math').sin(a)))
        normals.append((0, 1, 0))

    # Side vertices (duplicated for correct normals)
    side_start = len(verts)
    for i in range(segments):
        a = 2 * 3.14159 * i / segments
        nx = __import__('math').cos(a)
        nz = __import__('math').sin(a)
        verts.append((r * nx, -h, r * nz))
        normals.append((nx, 0, nz))
        verts.append((r * nx, h, r * nz))
        normals.append((nx, 0, nz))

    # Bottom cap triangles
    for i in range(segments):
        i0 = 1 + i
        i1 = 1 + (i + 1) % segments
        indices.append(bottom_center)
        indices.append(i0)
        indices.append(i1)
        face_normals_idx.append(0)
        face_normals_idx.append(0)
        face_normals_idx.append(0)

    # Top cap triangles
    for i in range(segments):
        i0 = top_start + i
        i1 = top_start + (i + 1) % segments
        indices.append(top_center)
        indices.append(i1)
        indices.append(i0)
        face_normals_idx.append(1)
        face_normals_idx.append(1)
        face_normals_idx.append(1)

    # Side triangles (2 per quad)
    for i in range(segments):
        a = side_start + i * 2
        b = side_start + i * 2 + 1
        a_next = side_start + ((i + 1) % segments) * 2
        b_next = side_start + ((i + 1) % segments) * 2 + 1
        indices.append(a)
        indices.append(b)
        indices.append(a_next)
        indices.append(a_next)
        indices.append(b)
        indices.append(b_next)
        face_normals_idx.extend([2 + i, 2 + i, 2 + i, 2 + i, 2 + i, 2 + i])

    return _build_glb(verts, normals, indices, face_normals_idx, has_side_normals=True)


def _build_glb(verts, normals_list, indices, face_normals_idx, has_side_normals=False):
    """Build a minimal GLB binary file."""
    import struct

    # Build accessor data
    pos_data = b''
    for v in verts:
        pos_data += struct.pack('<fff', v[0], v[1], v[2])

    normal_data = b''
    if has_side_normals:
        # Use per-vertex normals as-is
        for n in normals_list:
            normal_data += struct.pack('<fff', n[0], n[1], n[2])
    else:
        for ni in face_normals_idx:
            n = normals_list[ni]
            normal_data += struct.pack('<fff', n[0], n[1], n[2])

    index_data = b''
    for i in indices:
        index_data += struct.pack('<H', i)  # unsigned short

    # Pad to 4 bytes
    def pad4(data):
        while len(data) % 4 != 0:
            data += b'\x00'
        return data

    pos_data = pad4(pos_data)
    normal_data = pad4(normal_data)
    index_data = pad4(index_data)

    # JSON chunk (GLTF)
    vertex_count = len(pos_data) // 12  # 3 floats × 4 bytes
    normal_count = len(normal_data) // 12
    index_count = len(index_data) // 2

    gltf = {
        "asset": {"version": "2.0", "generator": "cadrender-preview"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "NORMAL": 1,
                },
                "indices": 2,
            }]
        }],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,  # FLOAT
                "count": vertex_count,
                "type": "VEC3",
                "min": [-0.5, -0.5, -0.5],
                "max": [0.5, 0.5, 0.5],
            },
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": normal_count,
                "type": "VEC3",
            },
            {
                "bufferView": 2,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": index_count,
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_data), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos_data), "byteLength": len(normal_data), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos_data) + len(normal_data), "byteLength": len(index_data), "target": 34963},
        ],
        "buffers": [{
            "byteLength": len(pos_data) + len(normal_data) + len(index_data),
        }],
    }

    json_str = json.dumps(gltf, separators=(',', ':'))
    json_bytes = json_str.encode('utf-8')
    json_bytes = pad4(json_bytes)

    # GLB structure
    total_len = 12 + 8 + len(json_bytes) + 8 + len(pos_data) + len(normal_data) + len(index_data)

    glb = b'glTF'
    glb += _pack_uint32(2)  # version
    glb += _pack_uint32(total_len)

    # JSON chunk
    glb += _pack_uint32(len(json_bytes))
    glb += b'JSON'
    glb += json_bytes

    # BIN chunk
    bin_len = len(pos_data) + len(normal_data) + len(index_data)
    glb += _pack_uint32(bin_len)
    glb += b'BIN\0'
    glb += pos_data
    glb += normal_data
    glb += index_data

    return glb


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python generate_preview_glb.py <cube|cylinder> <output_path>")
        sys.exit(1)

    shape = sys.argv[1]
    output = sys.argv[2]

    if shape == 'cube':
        data = _make_cube_glb()
    elif shape == 'cylinder':
        data = _make_cylinder_glb()
    else:
        print(f"Unknown shape: {shape}")
        sys.exit(1)

    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    with open(output, 'wb') as f:
        f.write(data)
    print(f"Generated {shape} GLB → {output} ({len(data)} bytes)")
