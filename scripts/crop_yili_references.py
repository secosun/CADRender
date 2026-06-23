"""Crop Yili color card photos into individual swatch references for texture calibration.

Usage:
    python scripts/crop_yili_references.py

Output:
    outputs/yili_crops/<finish_id>/<finish_id>_<n>.png — individual swatch crops
    outputs/yili_crops/<finish_id>/<finish_id>_crop.png — best representative crop
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

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
    """Attempt to extract individual color swatches from a Yili color card photo.

    Uses edge detection to find swatch boundaries, or falls back to grid division.
    """
    h, w = image.shape[:2]
    crops: list[tuple[np.ndarray, int, int]] = []

    # Try to find swatches via edge detection
    gray = np.mean(image, axis=2).astype(np.float32) if image.ndim == 3 else image.astype(np.float32)
    # Simple horizontal + vertical edge detection
    h_edges = np.abs(gray[:, 1:] - gray[:, :-1]).mean(axis=0)
    v_edges = np.abs(gray[1:, :] - gray[:-1, :]).mean(axis=1)

    # Find gaps (low edge areas) to determine swatch boundaries
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

    # If edge detection found too few or too many boundaries, fall back to grid
    if len(x_bounds) < 3 or len(y_bounds) < 3 or len(x_bounds) > 20 or len(y_bounds) > 20:
        # Fall back: divide into grid
        step_x = w // n_cols
        step_y = h // n_rows
        for row in range(n_rows):
            for col in range(n_cols):
                x1, x2 = col * step_x, (col + 1) * step_x
                y1, y2 = row * step_y, (row + 1) * step_y
                crop = image[y1:y2, x1:x2]
                # Skip if too uniform (likely background)
                if crop.std() > 15:
                    crops.append((crop, x1, y1))
        return crops

    # Extract swatches from the detected boundaries
    margin = 5  # px margin
    for yi in range(len(y_bounds) - 1):
        for xi in range(len(x_bounds) - 1):
            y1 = max(0, y_bounds[yi] + margin)
            y2 = min(h, y_bounds[yi + 1] - margin)
            x1 = max(0, x_bounds[xi] + margin)
            x2 = min(w, x_bounds[xi + 1] - margin)
            if y2 - y1 > 20 and x2 - x1 > 20:  # Minimum swatch size
                crop = image[y1:y2, x1:x2]
                # Skip background (too uniform or too white)
                if crop.std() > 15 and np.mean(crop) < 240:
                    crops.append((crop, x1, y1))

    return crops


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for series_dir, finish_id in sorted(SERIES_MAP.items()):
        series_path = YILI_DIR / series_dir
        if not series_path.is_dir():
            print(f"SERIES NOT FOUND: {series_dir}")
            continue

        # Use the 01.jpg as the primary reference image
        img_files = sorted(series_path.glob("*.jpg")) + sorted(series_path.glob("*.png"))
        if not img_files:
            print(f"  No images in {series_dir}")
            continue

        ref_img_path = img_files[0]  # First image as reference
        print(f"\n{series_dir} → {finish_id}")
        print(f"  Using: {ref_img_path.name}")

        img = np.array(Image.open(ref_img_path).convert("RGB"))
        crops = crop_swatches(img)

        finish_dir = finish_out_dir(OUT_DIR, finish_id)
        finish_dir.mkdir(parents=True, exist_ok=True)

        if not crops:
            print(f"  WARNING: No swatches detected, saving full center crop")
            h, w = img.shape[:2]
            y0, y1 = h // 4, 3 * h // 4
            x0, x1 = w // 4, 3 * w // 4
            center = img[y0:y1, x0:x1]
            out_path = finish_dir / f"{finish_id}_crop.png"
            Image.fromarray(center).save(out_path)
            print(f"  -> {out_path.name}")
            continue

        # Save individual swatches
        for i, (crop, cx, cy) in enumerate(crops[:8]):  # Max 8 per image
            out_path = finish_dir / f"{finish_id}_{i:02d}.png"
            Image.fromarray(crop).save(out_path)

        # Save the most representative crop (largest non-background area)
        best = max(crops, key=lambda x: x[0].shape[0] * x[0].shape[1])
        out_path = finish_dir / f"{finish_id}_crop.png"
        Image.fromarray(best[0]).save(out_path)
        print(f"  -> {len(crops)} swatches, best crops saved")

    print(f"\nDone. All reference crops in {OUT_DIR}")


if __name__ == "__main__":
    main()
