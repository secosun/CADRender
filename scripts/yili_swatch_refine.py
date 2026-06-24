"""Refine Yili swatch crops: quality filter → texture consensus → representative crop.

Pipeline:
  1. Score each swatch (white ratio, texture std, edge energy); drop worst 30%.
  2. Extract texture features on survivors; mean vector; drop high-fluctuation outliers.
  3. Write medoid crop as <finish_id>_crop.png (+ optional mean image + JSON report).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
_BW_SRC = REPO / "blenderworker" / "src"
if str(_BW_SRC) not in sys.path:
    sys.path.insert(0, str(_BW_SRC))

from core.texture_features import extract_texture_features  # noqa: E402
from orchestration.calibration.shared.scoring_reference import preprocess_for_texture_compare  # noqa: E402


def finish_out_dir(base: Path, finish_id: str) -> Path:
    return base / finish_id


@dataclass
class SwatchItem:
    index: int
    rgb: np.ndarray
    meta: dict[str, float] = field(default_factory=dict)
    abs_x: int = 0
    abs_y: int = 0


@dataclass
class RefineResult:
    selected: list[SwatchItem]
    rejected_quality: list[SwatchItem]
    rejected_outlier: list[SwatchItem]
    rejected_brightness: list[SwatchItem] = field(default_factory=list)
    rejected_glare: list[SwatchItem] = field(default_factory=list)
    mean_feature: np.ndarray | None = None
    medoid_index: int = -1
    quality_scores: dict[int, float] = field(default_factory=dict)
    outlier_distances: dict[int, float] = field(default_factory=dict)
    brightness_stats: dict[int, dict[str, float]] = field(default_factory=dict)
    glare_stats: dict[int, dict[str, float]] = field(default_factory=dict)


def _is_white(rgb: np.ndarray, threshold: float = 232.0) -> np.ndarray:
    if rgb.ndim == 2:
        return rgb > threshold
    return np.all(rgb.astype(np.float32) > threshold, axis=-1)


def swatch_brightness_stats(rgb: np.ndarray, white_thresh: float = 232.0) -> dict[str, float]:
    """Material-region brightness — used to drop shadow-heavy / near-black crops."""
    white = _is_white(rgb, white_thresh)
    mat_mask = ~white
    mat_ratio = float(mat_mask.mean())
    if int(mat_mask.sum()) < 30:
        return {
            "material_ratio": mat_ratio,
            "material_mean": 0.0,
            "dark_frac": 1.0,
            "center_mean": 0.0,
            "white_ratio": float(white.mean()),
        }

    mat = rgb[mat_mask]
    gray = mat.astype(np.float32).mean(axis=-1) if mat.ndim == 3 else mat.astype(np.float32)
    material_mean = float(gray.mean())
    dark_frac = float((gray < 30.0).mean())

    h, w = rgb.shape[:2]
    cy0, cy1 = h // 4, (3 * h) // 4
    cx0, cx1 = w // 4, (3 * w) // 4
    center = rgb[cy0:cy1, cx0:cx1]
    cw = _is_white(center, white_thresh)
    cmat = center[~cw]
    if cmat.size == 0:
        center_mean = 0.0
    elif cmat.ndim == 3:
        center_mean = float(cmat.astype(np.float32).mean())
    else:
        center_mean = float(cmat.astype(np.float32).mean())

    return {
        "material_ratio": mat_ratio,
        "material_mean": material_mean,
        "dark_frac": dark_frac,
        "center_mean": center_mean,
        "white_ratio": float(white.mean()),
    }


def swatch_passes_brightness_gate(
    stats: dict[str, float],
    *,
    min_material_ratio: float = 0.55,
    min_material_mean: float = 38.0,
    max_dark_frac: float = 0.48,
    min_center_mean: float = 32.0,
    max_white_ratio: float = 0.35,
) -> bool:
    return (
        stats["material_ratio"] >= min_material_ratio
        and stats["material_mean"] >= min_material_mean
        and stats["dark_frac"] <= max_dark_frac
        and stats["center_mean"] >= min_center_mean
        and stats["white_ratio"] <= max_white_ratio
    )


def swatch_glare_stats(
    rgb: np.ndarray,
    *,
    white_thresh: float = 232.0,
    specular_thresh: float = 243.0,
    clip_thresh: float = 251.0,
) -> dict[str, float]:
    """Detect specular glare / highlight blowout on center swatch (classical CV, no AI)."""
    h, w = rgb.shape[:2]
    cy0, cy1 = h // 4, (3 * h) // 4
    cx0, cx1 = w // 4, (3 * w) // 4
    patch = rgb[cy0:cy1, cx0:cx1]

    if rgb.ndim == 3:
        gray = patch.astype(np.float32).mean(axis=-1)
        max_ch = patch.astype(np.float32).max(axis=-1)
        min_ch = patch.astype(np.float32).min(axis=-1)
        card_white = min_ch > 249.0
    else:
        gray = patch.astype(np.float32)
        max_ch = gray
        card_white = gray > 249.0

    paint_mask = ~card_white
    if int(paint_mask.sum()) < 30:
        paint_mask = np.ones(max_ch.shape, dtype=bool)

    mat_gray = gray[paint_mask]
    mat_max = max_ch[paint_mask]
    specular_frac = float((mat_max >= specular_thresh).mean())
    clip_frac = float((max_ch >= clip_thresh).mean())
    material_std = float(mat_gray.std())
    center_mean = float(mat_gray.mean())
    center_specular_frac = specular_frac

    blowout_score = 0.0
    if center_mean > 200.0 and material_std < 18.0:
        blowout_score = float(min(1.0, max(0.0, (center_mean - 200.0) / 55.0)))

    bright = (max_ch >= specular_thresh) & paint_mask
    glare_ring_ratio = 0.0
    if bright.any():
        ring = np.zeros_like(bright, dtype=bool)
        ring[1:, :] |= bright[:-1, :]
        ring[:-1, :] |= bright[1:, :]
        ring[:, 1:] |= bright[:, :-1]
        ring[:, :-1] |= bright[:, 1:]
        ring &= paint_mask & ~bright
        ring_gray = gray[ring]
        if ring_gray.size > 20:
            glare_ring_ratio = float((ring_gray < mat_gray.mean() * 0.72).mean())

    return {
        "specular_frac": specular_frac,
        "clip_frac": clip_frac,
        "center_specular_frac": center_specular_frac,
        "center_mean": center_mean,
        "material_std": material_std,
        "blowout_score": blowout_score,
        "glare_ring_ratio": glare_ring_ratio,
    }


def swatch_passes_glare_gate(
    stats: dict[str, float],
    *,
    max_specular_frac: float = 0.10,
    max_clip_frac: float = 0.025,
    max_center_specular_frac: float = 0.18,
    max_blowout_score: float = 0.55,
    max_glare_ring_ratio: float = 0.42,
    max_center_mean_blowout: float = 235.0,
    min_std_when_bright: float = 15.0,
) -> bool:
    if stats["clip_frac"] > max_clip_frac:
        return False
    if stats["specular_frac"] > max_specular_frac:
        return False
    if stats["center_specular_frac"] > max_center_specular_frac:
        return False
    if stats["blowout_score"] > max_blowout_score:
        return False
    if stats["glare_ring_ratio"] > max_glare_ring_ratio:
        return False
    if (
        stats["center_mean"] > max_center_mean_blowout
        and stats["material_std"] < min_std_when_bright
    ):
        return False
    return True


def swatch_quality_score(rgb: np.ndarray, white_thresh: float = 232.0) -> dict[str, float]:
    """Heuristic quality for phase-1 rejection (higher score = better)."""
    bright = swatch_brightness_stats(rgb, white_thresh)
    glare = swatch_glare_stats(rgb, white_thresh=white_thresh)
    white_ratio = bright["white_ratio"]
    mat = rgb[~_is_white(rgb, white_thresh)]
    if mat.size < 30:
        return {**bright, **glare, "std": 0.0, "edge": 0.0, "score": -1.0}

    if mat.ndim == 3:
        gray = mat.astype(np.float32).mean(axis=-1)
    else:
        gray = mat.astype(np.float32)
    std = float(gray.std())

    g = rgb.astype(np.float32).mean(axis=-1)
    gx = np.abs(g[:, 1:] - g[:, :-1])
    gy = np.abs(g[1:, :] - g[:-1, :])
    edge = float((gx.mean() + gy.mean()) / 2.0)

    std_term = min(std, 80.0)
    score = (
        std_term * (1.0 - white_ratio)
        + edge * 0.35
        - white_ratio * 50.0
        + bright["material_mean"] * 0.12
        - bright["dark_frac"] * 45.0
        - glare["specular_frac"] * 120.0
        - glare["clip_frac"] * 200.0
        - glare["blowout_score"] * 35.0
    )
    return {
        **bright,
        **glare,
        "std": std,
        "edge": edge,
        "score": score,
    }


def _resize_rgb(rgb: np.ndarray, size: int) -> np.ndarray:
    return np.array(Image.fromarray(rgb).resize((size, size), Image.Resampling.LANCZOS))


def _feature_vector(rgb: np.ndarray) -> np.ndarray:
    proc = preprocess_for_texture_compare(rgb)
    feats = extract_texture_features(proc, image_is_srgb=False)
    return feats["feature_vector"]


def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    dot = float(np.dot(a, b))
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-8 or nb < 1e-8:
        return 1.0
    return 1.0 - dot / (na * nb)


def refine_swatches(
    items: list[SwatchItem],
    *,
    reject_fraction: float = 0.3,
    outlier_mad_factor: float = 2.5,
    min_keep: int = 2,
    mean_thumb_size: int = 128,
    brightness_gate: bool = True,
    glare_gate: bool = True,
) -> RefineResult:
    """Drop shadow/glare swatches, then worst ``reject_fraction``, then texture outliers."""
    if not items:
        return RefineResult(selected=[], rejected_quality=[], rejected_outlier=[])

    brightness_stats: dict[int, dict[str, float]] = {}
    glare_stats: dict[int, dict[str, float]] = {}
    rejected_brightness: list[SwatchItem] = []
    rejected_glare: list[SwatchItem] = []
    candidates: list[SwatchItem] = []
    for item in items:
        stats = swatch_brightness_stats(item.rgb)
        gstats = swatch_glare_stats(item.rgb)
        brightness_stats[item.index] = stats
        glare_stats[item.index] = gstats
        item.meta.update(stats)
        item.meta.update(gstats)
        if brightness_gate and not swatch_passes_brightness_gate(stats):
            rejected_brightness.append(item)
        elif glare_gate and not swatch_passes_glare_gate(gstats):
            rejected_glare.append(item)
        else:
            candidates.append(item)

    pool = candidates if len(candidates) >= min_keep else list(items)

    scored: list[tuple[SwatchItem, float, dict]] = []
    for item in pool:
        q = swatch_quality_score(item.rgb)
        item.meta.update(q)
        scored.append((item, q["score"], q))

    scored.sort(key=lambda x: x[1], reverse=True)
    n_remove = max(0, int(round(len(scored) * reject_fraction)))
    n_keep = max(min_keep, len(scored) - n_remove)
    n_keep = min(n_keep, len(scored))

    kept = [s[0] for s in scored[:n_keep]]
    rejected_q = [s[0] for s in scored[n_keep:]]

    quality_scores = {it.index: float(sc) for it, sc, _ in scored}

    if len(kept) <= 1:
        medoid = kept[0] if kept else items[0]
        return RefineResult(
            selected=kept,
            rejected_quality=rejected_q,
            rejected_outlier=[],
            rejected_brightness=rejected_brightness,
            rejected_glare=rejected_glare,
            medoid_index=medoid.index,
            quality_scores=quality_scores,
            brightness_stats=brightness_stats,
            glare_stats=glare_stats,
        )

    feat_vecs = [_feature_vector(it.rgb) for it in kept]
    mean_vec = np.mean(feat_vecs, axis=0)
    norm = float(np.linalg.norm(mean_vec))
    if norm > 1e-8:
        mean_vec = mean_vec / norm

    distances = [_cosine_distance(fv, mean_vec) for fv in feat_vecs]
    outlier_dist = {it.index: float(d) for it, d in zip(kept, distances)}

    med = float(np.median(distances))
    mad = float(np.median(np.abs(np.array(distances) - med)))
    if mad < 1e-6:
        threshold = med + 0.05
    else:
        threshold = med + outlier_mad_factor * mad

    selected: list[SwatchItem] = []
    rejected_o: list[SwatchItem] = []
    for item, dist in zip(kept, distances):
        if dist <= threshold:
            selected.append(item)
        else:
            rejected_o.append(item)

    if len(selected) < min_keep and len(kept) >= min_keep:
        # MAD too aggressive — keep closest-to-mean swatches
        order = sorted(zip(kept, distances), key=lambda x: x[1])
        selected = [x[0] for x in order[:min_keep]]
        rejected_o = [x[0] for x in order[min_keep:]]

    medoid_idx = -1
    if selected:
        sel_dists = [
            _cosine_distance(_feature_vector(it.rgb), mean_vec) for it in selected
        ]
        medoid_idx = selected[int(np.argmin(sel_dists))].index

    return RefineResult(
        selected=selected,
        rejected_quality=rejected_q,
        rejected_outlier=rejected_o,
        rejected_brightness=rejected_brightness,
        rejected_glare=rejected_glare,
        mean_feature=mean_vec,
        medoid_index=medoid_idx,
        quality_scores=quality_scores,
        outlier_distances=outlier_dist,
        brightness_stats=brightness_stats,
        glare_stats=glare_stats,
    )


def mean_rgb_image(items: list[SwatchItem], size: int = 128) -> np.ndarray:
    if not items:
        raise ValueError("no swatches for mean image")
    stack = np.stack([_resize_rgb(it.rgb, size) for it in items], axis=0)
    return np.clip(stack.mean(axis=0), 0, 255).astype(np.uint8)


def save_refine_outputs(
    result: RefineResult,
    finish_dir: Path,
    finish_id: str,
    *,
    source_rgb: np.ndarray | None = None,
    mat_bbox: tuple[int, int, int, int] | None = None,
    roi: tuple[int, int, int, int] | None = None,
    all_items: list[SwatchItem] | None = None,
    mean_thumb_size: int = 128,
) -> Path:
    finish_dir.mkdir(parents=True, exist_ok=True)

    medoid_path = finish_dir / f"{finish_id}_crop.png"
    mean_path = finish_dir / f"{finish_id}_crop_mean.png"
    report_path = finish_dir / f"{finish_id}_refine_report.json"

    if result.selected:
        medoid = next(
            (it for it in result.selected if it.index == result.medoid_index),
            result.selected[0],
        )
        Image.fromarray(medoid.rgb).save(medoid_path)
        Image.fromarray(mean_rgb_image(result.selected, mean_thumb_size)).save(mean_path)

    report: dict[str, Any] = {
        "finish_id": finish_id,
        "n_input": len(all_items) if all_items else (
            len(result.selected) + len(result.rejected_quality) + len(result.rejected_outlier)
        ),
        "n_selected": len(result.selected),
        "n_rejected_quality": len(result.rejected_quality),
        "n_rejected_outlier": len(result.rejected_outlier),
        "n_rejected_brightness": len(result.rejected_brightness),
        "n_rejected_glare": len(result.rejected_glare),
        "selected_indices": [it.index for it in result.selected],
        "rejected_quality_indices": [it.index for it in result.rejected_quality],
        "rejected_outlier_indices": [it.index for it in result.rejected_outlier],
        "rejected_brightness_indices": [it.index for it in result.rejected_brightness],
        "rejected_glare_indices": [it.index for it in result.rejected_glare],
        "medoid_index": result.medoid_index,
        "quality_scores": result.quality_scores,
        "outlier_distances": result.outlier_distances,
        "brightness_stats": {str(k): v for k, v in result.brightness_stats.items()},
        "glare_stats": {str(k): v for k, v in result.glare_stats.items()},
        "crop_path": str(medoid_path),
        "crop_mean_path": str(mean_path),
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if source_rgb is not None and mat_bbox is not None and roi is not None and all_items:
        debug_path = finish_dir / f"{finish_id}_14_refine_debug.png"
        _save_refine_debug(
            source_rgb,
            mat_bbox,
            roi,
            all_items,
            result,
            debug_path,
        )
        report["refine_debug_path"] = str(debug_path)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report_path


def _save_refine_debug(
    rgb: np.ndarray,
    mat_bbox: tuple[int, int, int, int],
    roi: tuple[int, int, int, int],
    all_items: list[SwatchItem],
    result: RefineResult,
    path: Path,
) -> None:
    img = Image.fromarray(rgb.copy())
    draw = ImageDraw.Draw(img)
    x0, y0, x1, y1 = mat_bbox
    draw.rectangle([x0, y0, x1, y1], outline=(0, 200, 255), width=2)
    rx0, ry0, rx1, ry1 = roi
    draw.rectangle([rx0, ry0, rx1, ry1], outline=(255, 180, 0), width=3)

    sel = {it.index for it in result.selected}
    rej_q = {it.index for it in result.rejected_quality}
    rej_o = {it.index for it in result.rejected_outlier}
    rej_b = {it.index for it in result.rejected_brightness}
    rej_g = {it.index for it in result.rejected_glare}

    for item in all_items:
        ch, cw = item.rgb.shape[:2]
        sx, sy = item.abs_x, item.abs_y
        if item.index in sel:
            color = (0, 255, 0)
            width = 3 if item.index == result.medoid_index else 2
        elif item.index in rej_g:
            color = (255, 128, 0)
            width = 2
        elif item.index in rej_b:
            color = (255, 0, 255)
            width = 2
        elif item.index in rej_q:
            color = (255, 200, 0)
            width = 2
        elif item.index in rej_o:
            color = (255, 0, 0)
            width = 2
        else:
            color = (180, 180, 180)
            width = 1
        draw.rectangle([sx, sy, sx + cw, sy + ch], outline=color, width=width)

    img.save(path)


def load_swatches_from_dir(finish_dir: Path, finish_id: str) -> list[SwatchItem]:
    items: list[SwatchItem] = []
    for path in sorted(finish_dir.glob(f"{finish_id}_*.png")):
        name = path.stem
        if name in {
            f"{finish_id}_crop",
            f"{finish_id}_crop_mean",
            f"{finish_id}_14_debug",
            f"{finish_id}_14_refine_debug",
        } or "_debug" in name:
            continue
        suffix = name[len(finish_id) + 1:]
        if not suffix.isdigit():
            continue
        idx = int(suffix)
        rgb = np.array(Image.open(path).convert("RGB"))
        items.append(SwatchItem(index=idx, rgb=rgb))
    return items
