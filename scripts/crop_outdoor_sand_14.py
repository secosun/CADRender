#!/usr/bin/env python3
"""Crop outdoor_sand reference from 蚁力 14.jpg — vertical middle 3/5 ROI, 3×3 swatches.

Skips top/bottom 1/5 of material bbox; avoids white background.

Usage:
    python scripts/crop_outdoor_sand_14.py
    python scripts/crop_outdoor_sand_14.py --image "outputs/蚁力色卡/01-户外砂纹系列/14.jpg"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = REPO / "outputs" / "蚁力色卡" / "01-户外砂纹系列" / "14.jpg"
OUT_DIR = REPO / "outputs" / "yili_crops"
FINISH_ID = "outdoor_sand"


def finish_out_dir(base: Path, finish_id: str) -> Path:
    """Per-finish crop folder: outputs/yili_crops/<finish_id>/"""
    return base / finish_id


def _is_white(rgb: np.ndarray, threshold: float = 232.0) -> np.ndarray:
    """True where pixel is near white background."""
    if rgb.ndim == 2:
        return rgb > threshold
    return np.all(rgb.astype(np.float32) > threshold, axis=-1)


def material_mask(rgb: np.ndarray, white_thresh: float = 232.0) -> np.ndarray:
    return ~_is_white(rgb, white_thresh)


def material_bbox(mask: np.ndarray, min_area: int = 500) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if len(xs) < min_area:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def material_middle_roi(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    y_start_frac: float = 0.2,
    y_end_frac: float = 0.8,
) -> tuple[int, int, int, int]:
    """Vertical middle band: exclude top 1/5 and bottom 1/5, keep central 3/5."""
    h = y1 - y0
    ry0 = y0 + int(h * y_start_frac)
    ry1 = y0 + int(h * y_end_frac)
    return x0, ry0, x1, ry1


def tighten_roi_to_material(
    mask: np.ndarray,
    roi: tuple[int, int, int, int],
    min_pixels: int = 200,
) -> tuple[int, int, int, int]:
    """Shrink ROI horizontally to actual material pixels in the vertical band."""
    x0, y0, x1, y1 = roi
    sub = mask[y0:y1, x0:x1]
    ys, xs = np.where(sub)
    if len(xs) < min_pixels:
        return roi
    lx = int(xs.min())
    rx = int(xs.max()) + 1
    return x0 + lx, y0, x0 + rx, y1


def center_face_roi(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    y_start_frac: float = 0.38,
    y_end_frac: float = 0.92,
    x_center_frac: float = 0.5,
    x_half_width_frac: float = 0.24,
) -> tuple[int, int, int, int]:
    """Center vertical strip on profile face (skip side flanges / white gaps)."""
    w = x1 - x0
    h = y1 - y0
    cx = x0 + int(w * x_center_frac)
    half = max(8, int(w * x_half_width_frac))
    rx0 = max(x0, cx - half)
    rx1 = min(x1, cx + half)
    ry0 = y0 + int(h * y_start_frac)
    ry1 = y0 + int(h * y_end_frac)
    return rx0, ry0, rx1, ry1


def cell_quality(cell: np.ndarray, white_thresh: float = 232.0) -> dict[str, float]:
    white = _is_white(cell, white_thresh)
    white_ratio = float(white.mean())
    mat = cell[~white]
    if mat.size < 30:
        return {"white_ratio": white_ratio, "std": 0.0, "score": -1.0}
    gray = mat.astype(np.float32)
    if gray.ndim == 2:
        vals = gray
    else:
        vals = gray.mean(axis=-1)
    std = float(vals.std())
    # Prefer textured, non-white cells
    score = std * (1.0 - white_ratio) - white_ratio * 50.0
    return {"white_ratio": white_ratio, "std": std, "score": score}


def _tight_material_crop(
    cell_rgb: np.ndarray,
    cell_mask: np.ndarray,
    min_pixels: int = 120,
    *,
    min_luma: float = 28.0,
) -> np.ndarray | None:
    """Tight bbox on material; drop near-black shadow pixels inside the cell."""
    if int(cell_mask.sum()) < min_pixels:
        return None
    gray = cell_rgb.astype(np.float32).mean(axis=-1)
    good = cell_mask & (gray >= min_luma)
    if int(good.sum()) < min_pixels:
        good = cell_mask
    ys, xs = np.where(good)
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    crop = cell_rgb[y0:y1, x0:x1]
    if crop.shape[0] < 12 or crop.shape[1] < 12:
        return None
    return crop


def sample_grid(
    rgb: np.ndarray,
    mask: np.ndarray,
    roi: tuple[int, int, int, int],
    n_cols: int = 3,
    n_rows: int = 3,
    *,
    inner_margin_frac: float = 0.03,
    min_material_ratio: float = 0.35,
    min_std: float = 8.0,
    white_thresh: float = 232.0,
) -> list[tuple[np.ndarray, int, int, dict]]:
    x0, y0, x1, y1 = roi
    w, h = x1 - x0, y1 - y0
    mx = int(w * inner_margin_frac)
    my = int(h * inner_margin_frac)
    inner_rgb = rgb[y0 + my:y1 - my, x0 + mx:x1 - mx]
    inner_mask = mask[y0 + my:y1 - my, x0 + mx:x1 - mx]
    ih, iw = inner_rgb.shape[:2]
    cell_w = max(1, iw // n_cols)
    cell_h = max(1, ih // n_rows)

    out: list[tuple[np.ndarray, int, int, dict]] = []
    for row in range(n_rows):
        for col in range(n_cols):
            cx0 = col * cell_w
            cy0 = row * cell_h
            cx1 = (col + 1) * cell_w if col < n_cols - 1 else iw
            cy1 = (row + 1) * cell_h if row < n_rows - 1 else ih
            cell_rgb = inner_rgb[cy0:cy1, cx0:cx1]
            cell_m = inner_mask[cy0:cy1, cx0:cx1]
            material_ratio = float(cell_m.mean())
            if material_ratio < min_material_ratio:
                continue
            crop = _tight_material_crop(cell_rgb, cell_m)
            if crop is None:
                continue
            q = cell_quality(crop, white_thresh)
            if q["std"] < min_std:
                continue
            q["material_ratio"] = material_ratio
            ys_m, xs_m = np.where(cell_m)
            abs_x = x0 + mx + cx0 + int(xs_m.min())
            abs_y = y0 + my + cy0 + int(ys_m.min())
            out.append((crop, abs_x, abs_y, q))

    return out


def save_debug_overlay(
    rgb: np.ndarray,
    mat_bbox: tuple[int, int, int, int],
    roi: tuple[int, int, int, int],
    samples: list[tuple[np.ndarray, int, int, dict]],
    path: Path,
) -> None:
    img = Image.fromarray(rgb.copy())
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = mat_bbox
    draw.rectangle([x0, y0, x1, y1], outline=(0, 200, 255), width=2)
    rx0, ry0, rx1, ry1 = roi
    draw.rectangle([rx0, ry0, rx1, ry1], outline=(255, 180, 0), width=3)
    for crop, sx, sy, _ in samples:
        ch, cw = crop.shape[:2]
        draw.rectangle([sx, sy, sx + cw, sy + ch], outline=(0, 255, 0), width=2)
    img.save(path)


def run(
    image_path: Path,
    finish_id: str = FINISH_ID,
    out_dir: Path = OUT_DIR,
    n_cols: int = 3,
    n_rows: int = 3,
) -> int:
    if not image_path.is_file():
        print(f"ERROR: image not found: {image_path}")
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    finish_dir = finish_out_dir(out_dir, finish_id)
    finish_dir.mkdir(parents=True, exist_ok=True)
    rgb = np.array(Image.open(image_path).convert("RGB"))
    mask = material_mask(rgb)
    bbox = material_bbox(mask)
    if bbox is None:
        print("ERROR: no material region detected (all white?)")
        return 1

    roi = material_middle_roi(*bbox)
    roi = tighten_roi_to_material(mask, roi)
    roi = center_face_roi(*roi)
    roi = tighten_roi_to_material(mask, roi)
    samples = sample_grid(rgb, mask, roi, n_cols=n_cols, n_rows=n_rows)

    if len(samples) < n_cols * n_rows:
        samples = sample_grid(
            rgb, mask, roi, n_cols=n_cols, n_rows=n_rows,
            min_material_ratio=0.55, min_std=6.0,
        )

    if not samples:
        print("ERROR: no valid swatches after white filter; check ROI")
        return 1

    # Sort by grid position (row, col) for stable 00–08 indices
    cell_w = max(1, (roi[2] - roi[0]) // n_cols)
    cell_h = max(1, (roi[3] - roi[1]) // n_rows)
    samples.sort(key=lambda s: ((s[2] - roi[1]) // cell_h, (s[1] - roi[0]) // cell_w))

    for i, (crop, sx, sy, q) in enumerate(samples[:n_cols * n_rows]):
        out_path = finish_dir / f"{finish_id}_{i:02d}.png"
        Image.fromarray(crop).save(out_path)
        mat = q.get("material_ratio", 0)
        print(f"  {out_path.name}  mat={mat:.0%} std={q['std']:.1f}")

    # Phase 1+2: drop worst 30% by quality, then texture-outliers from mean feature
    import sys
    _scripts = Path(__file__).resolve().parent
    if str(_scripts) not in sys.path:
        sys.path.insert(0, str(_scripts))
    from yili_swatch_refine import SwatchItem, refine_swatches, save_refine_outputs

    swatch_items = [
        SwatchItem(i, crop, dict(q), sx, sy)
        for i, (crop, sx, sy, q) in enumerate(samples[:n_cols * n_rows])
    ]
    refine_result = refine_swatches(swatch_items, reject_fraction=0.3)
    report_path = save_refine_outputs(
        refine_result,
        finish_dir,
        finish_id,
        source_rgb=rgb,
        mat_bbox=bbox,
        roi=roi,
        all_items=swatch_items,
    )
    print(
        f"  refine: selected {len(refine_result.selected)}/{len(swatch_items)}"
        f"  medoid={refine_result.medoid_index}"
        f"  rejected_b={[it.index for it in refine_result.rejected_brightness]}"
        f"  rejected_q={[it.index for it in refine_result.rejected_quality]}"
        f"  rejected_o={[it.index for it in refine_result.rejected_outlier]}"
    )
    print(f"  -> report {report_path.name}")

    debug_path = finish_dir / f"{finish_id}_14_debug.png"
    save_debug_overlay(rgb, bbox, roi, samples, debug_path)
    print(f"  -> debug {debug_path.name}")

    meta_path = finish_dir / f"{finish_id}_14_source.txt"
    meta_path.write_text(
        f"source={image_path}\nroi={roi}\nmat_bbox={bbox}\nsamples={len(samples)}\n",
        encoding="utf-8",
    )
    print(f"\nDone: {len(samples)} swatches in {finish_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Crop outdoor_sand from 蚁力 14.jpg")
    p.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    p.add_argument("--finish-id", default=FINISH_ID)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--cols", type=int, default=3)
    p.add_argument("--rows", type=int, default=3)
    args = p.parse_args()
    return run(
        args.image.resolve(),
        finish_id=args.finish_id,
        out_dir=args.out_dir.resolve(),
        n_cols=args.cols,
        n_rows=args.rows,
    )


if __name__ == "__main__":
    raise SystemExit(main())
