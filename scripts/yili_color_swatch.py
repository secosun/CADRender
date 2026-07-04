"""Extract one texture patch per Yili color-card photo (same finish, different color)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np


def _is_white(rgb: np.ndarray, threshold: float = 232.0) -> np.ndarray:
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
    h = y1 - y0
    ry0 = y0 + int(h * y_start_frac)
    ry1 = y0 + int(h * y_end_frac)
    return x0, ry0, x1, ry1


def tighten_roi_to_material(
    mask: np.ndarray,
    roi: tuple[int, int, int, int],
    min_pixels: int = 200,
) -> tuple[int, int, int, int]:
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
    vals = gray if gray.ndim == 2 else gray.mean(axis=-1)
    std = float(vals.std())
    score = std * (1.0 - white_ratio) - white_ratio * 50.0
    return {"white_ratio": white_ratio, "std": std, "score": score}


def _tight_material_crop(
    cell_rgb: np.ndarray,
    cell_mask: np.ndarray,
    min_pixels: int = 120,
    *,
    min_luma: float = 28.0,
) -> np.ndarray | None:
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
) -> list[tuple[np.ndarray, dict[str, float]]]:
    x0, y0, x1, y1 = roi
    w, h = x1 - x0, y1 - y0
    mx = int(w * inner_margin_frac)
    my = int(h * inner_margin_frac)
    inner_rgb = rgb[y0 + my : y1 - my, x0 + mx : x1 - mx]
    inner_mask = mask[y0 + my : y1 - my, x0 + mx : x1 - mx]
    ih, iw = inner_rgb.shape[:2]
    cell_w = max(1, iw // n_cols)
    cell_h = max(1, ih // n_rows)

    out: list[tuple[np.ndarray, dict[str, float]]] = []
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
            out.append((crop, q))
    return out


def extract_best_texture_patch(
    rgb: np.ndarray,
    *,
    n_cols: int = 3,
    n_rows: int = 3,
) -> np.ndarray | None:
    """One representative texture crop from a single color-card photo."""
    mask = material_mask(rgb)
    bbox = material_bbox(mask)
    if bbox is None:
        h, w = rgb.shape[:2]
        center = rgb[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
        return center if center.std() > 12 else None

    roi = material_middle_roi(*bbox)
    roi = tighten_roi_to_material(mask, roi)
    roi = center_face_roi(*roi)
    roi = tighten_roi_to_material(mask, roi)
    samples = sample_grid(rgb, mask, roi, n_cols=n_cols, n_rows=n_rows)
    if not samples:
        samples = sample_grid(
            rgb, mask, roi, n_cols=n_cols, n_rows=n_rows,
            min_material_ratio=0.55, min_std=6.0,
        )
    if not samples:
        x0, y0, x1, y1 = roi
        fallback = rgb[y0:y1, x0:x1]
        return fallback if fallback.size and fallback.std() > 10 else None
    best_crop, _ = max(samples, key=lambda item: item[1]["score"])
    return best_crop


def color_index_from_filename(path: Path) -> str | None:
    """``01.jpg`` → ``01``; ``14.png`` → ``14``."""
    m = re.match(r"^(\d{1,2})$", path.stem)
    return m.group(1).zfill(2) if m else None
