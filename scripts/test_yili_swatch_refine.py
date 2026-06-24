"""Unit tests for Yili swatch glare / brightness gates."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from yili_swatch_refine import (  # noqa: E402
    swatch_glare_stats,
    swatch_passes_glare_gate,
    refine_swatches,
    SwatchItem,
)


def _flat_swatch(mean: float, size: int = 64) -> np.ndarray:
    v = int(np.clip(mean, 0, 255))
    return np.full((size, size, 3), v, dtype=np.uint8)


def test_glare_rejects_specular_blob():
    rgb = _flat_swatch(120)
    rgb[18:34, 18:34] = np.array([248, 238, 210], dtype=np.uint8)
    stats = swatch_glare_stats(rgb)
    assert stats["specular_frac"] > 0.04
    assert not swatch_passes_glare_gate(stats)


def test_glare_rejects_clip_saturation():
    rgb = _flat_swatch(130)
    rgb[15:35, 15:35] = 255
    stats = swatch_glare_stats(rgb)
    assert stats["clip_frac"] > 0.02
    assert not swatch_passes_glare_gate(stats)


def test_glare_passes_uniform_texture():
    rgb = _flat_swatch(140)
    noise = np.random.default_rng(0).integers(-12, 13, rgb.shape, dtype=np.int16)
    rgb = np.clip(rgb.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    stats = swatch_glare_stats(rgb)
    assert swatch_passes_glare_gate(stats)


def test_refine_swatches_rejects_glare_item():
    good = SwatchItem(index=0, rgb=_flat_swatch(130))
    bad = SwatchItem(index=1, rgb=_flat_swatch(130))
    bad.rgb[10:30, 10:30] = 255
    result = refine_swatches([good, bad], min_keep=1, reject_fraction=0.0)
    assert any(it.index == 1 for it in result.rejected_glare)
