"""Crop Yili color card photos into individual swatch references for texture calibration.

Usage:
    python scripts/crop_yili_references.py
    python scripts/crop_yili_references.py --multi-color-only outdoor_sand

Output:
    outputs/yili_crops/<finish_id>/<finish_id>_<n>.png — spatial grid from first card (legacy)
    outputs/yili_crops/<finish_id>/<finish_id>_colorNN.png — one patch per color JPG
    outputs/yili_crops/<finish_id>/color_swatches.json — manifest for scoring aggregation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from yili_color_swatch import color_index_from_filename, extract_best_texture_patch

# Map Yili series directories to finish IDs
SERIES_MAP = {
    "01-户外砂纹系列": "outdoor_sand",
    "02-户外微晶陶瓷系列": "microcrystalline",
    "03-户外超耐候系列": "super_weather_resistant",
    "04-户外爆花系列": "burst_pattern",
    "05-高端氟碳系列": "premium_fluorocarbon",
    "06-户外平面系列": "flat_smooth",
    "07-自喷修补漆": "repair_spray",
    "08-户外扫金漆系列": "gold_sweeping",
}

YILI_DIR = Path(__file__).resolve().parents[1] / "outputs" / "蚁力色卡"
OUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "yili_crops"


def finish_out_dir(base: Path, finish_id: str) -> Path:
    return base / finish_id


def crop_swatches(image: np.ndarray, n_cols: int = 4, n_rows: int = 4) -> list[tuple[np.ndarray, int, int]]:
    """Extract spatial swatches from one card photo (legacy grid / edge detect)."""
    h, w = image.shape[:2]
    crops: list[tuple[np.ndarray, int, int]] = []

    gray = np.mean(image, axis=2).astype(np.float32) if image.ndim == 3 else image.astype(np.float32)
    h_edges = np.abs(gray[:, 1:] - gray[:, :-1]).mean(axis=0)
    v_edges = np.abs(gray[1:, :] - gray[:-1, :]).mean(axis=1)

    def find_boundaries(edges: np.ndarray, threshold: float) -> list[int]:
        boundaries = [0]
        for i in range(1, len(edges) - 1):
            if edges[i] < threshold and edges[i - 1] >= threshold:
                boundaries.append(i)
        boundaries.append(len(edges))
        return boundaries

    h_thresh = np.percentile(h_edges, 30)
    v_thresh = np.percentile(v_edges, 30)
    x_bounds = find_boundaries(h_edges, h_thresh)
    y_bounds = find_boundaries(v_edges, v_thresh)

    if len(x_bounds) < 3 or len(y_bounds) < 3 or len(x_bounds) > 20 or len(y_bounds) > 20:
        step_x = w // n_cols
        step_y = h // n_rows
        for row in range(n_rows):
            for col in range(n_cols):
                x1, x2 = col * step_x, (col + 1) * step_x
                y1, y2 = row * step_y, (row + 1) * step_y
                crop = image[y1:y2, x1:x2]
                if crop.std() > 15:
                    crops.append((crop, x1, y1))
        return crops

    margin = 5
    for yi in range(len(y_bounds) - 1):
        for xi in range(len(x_bounds) - 1):
            y1 = max(0, y_bounds[yi] + margin)
            y2 = min(h, y_bounds[yi + 1] - margin)
            x1 = max(0, x_bounds[xi] + margin)
            x2 = min(w, x_bounds[xi + 1] - margin)
            if y2 - y1 > 20 and x2 - x1 > 20:
                crop = image[y1:y2, x1:x2]
                if crop.std() > 15 and np.mean(crop) < 240:
                    crops.append((crop, x1, y1))

    return crops


def crop_color_swatches_for_series(
    series_path: Path,
    finish_id: str,
    finish_dir: Path,
) -> list[dict[str, str]]:
    """One texture patch per numbered color JPG in the series folder."""
    img_files = sorted(series_path.glob("*.jpg")) + sorted(series_path.glob("*.png"))
    manifest: list[dict[str, str]] = []

    for img_path in img_files:
        color_idx = color_index_from_filename(img_path)
        if color_idx is None:
            continue
        rgb = np.array(Image.open(img_path).convert("RGB"))
        patch = extract_best_texture_patch(rgb)
        if patch is None:
            print(f"  skip {img_path.name}: no valid texture patch")
            continue
        out_name = f"{finish_id}_color{color_idx}.png"
        out_path = finish_dir / out_name
        Image.fromarray(patch).save(out_path)
        manifest.append(
            {
                "color_index": color_idx,
                "path": out_name,
                "source_jpg": img_path.name,
            }
        )
        print(f"  color {color_idx} <- {img_path.name}  {patch.shape[1]}x{patch.shape[0]} std={patch.std():.1f}")

    if manifest:
        manifest_path = finish_dir / "color_swatches.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "finish_id": finish_id,
                    "series_dir": series_path.name,
                    "n_colors": len(manifest),
                    "swatches": manifest,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return manifest


def crop_spatial_swatches(ref_img_path: Path, finish_id: str, finish_dir: Path) -> None:
    """Legacy: spatial grid from the first card image."""
    img = np.array(Image.open(ref_img_path).convert("RGB"))
    crops = crop_swatches(img)

    if not crops:
        print("  WARNING: No swatches detected, saving full center crop")
        h, w = img.shape[:2]
        center = img[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
        Image.fromarray(center).save(finish_dir / f"{finish_id}_crop.png")
        return

    for i, (crop, _cx, _cy) in enumerate(crops[:8]):
        Image.fromarray(crop).save(finish_dir / f"{finish_id}_{i:02d}.png")

    best = max(crops, key=lambda x: x[0].shape[0] * x[0].shape[1])
    Image.fromarray(best[0]).save(finish_dir / f"{finish_id}_crop.png")
    print(f"  spatial: {len(crops)} swatches from {ref_img_path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crop Yili color-card references")
    parser.add_argument(
        "--finish-id",
        action="append",
        dest="finish_ids",
        help="Only process these finish IDs (repeatable)",
    )
    parser.add_argument(
        "--skip-spatial",
        action="store_true",
        help="Skip legacy spatial grid from first JPG",
    )
    args = parser.parse_args()
    only_finishes = set(args.finish_ids or [])

    os.makedirs(OUT_DIR, exist_ok=True)

    for series_dir, finish_id in sorted(SERIES_MAP.items()):
        if only_finishes and finish_id not in only_finishes:
            continue

        series_path = YILI_DIR / series_dir
        if not series_path.is_dir():
            print(f"SERIES NOT FOUND: {series_dir}")
            continue

        img_files = sorted(series_path.glob("*.jpg")) + sorted(series_path.glob("*.png"))
        if not img_files:
            print(f"  No images in {series_dir}")
            continue

        print(f"\n{series_dir} → {finish_id}")
        finish_dir = finish_out_dir(OUT_DIR, finish_id)
        finish_dir.mkdir(parents=True, exist_ok=True)

        color_manifest = crop_color_swatches_for_series(series_path, finish_id, finish_dir)
        print(f"  -> {len(color_manifest)} color-invariant swatches")

        if not args.skip_spatial:
            crop_spatial_swatches(img_files[0], finish_id, finish_dir)

    print(f"\nDone. References in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
