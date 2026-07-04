#!/usr/bin/env python3
"""Compare single-ref vs multi-color proto scoring / warm-start for outdoor_sand."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "blenderworker" / "src"))

from orchestration.calibration.shared.scoring_reference import (
    mean_reference_texture_similarity,
    proto_reference_texture_similarity,
)
from orchestration.calibration.shared.texture_param_estimate import (
    estimate_texture_params,
    measure_reference_texture_stats,
)
from orchestration.calibration.shared.yili_references import resolve_texture_reference_paths
from orchestration.calibration.texture_engine import _defaults_from_bakecoat, _load_finish_cfg

G1 = _REPO / "outputs" / "yili_crops" / "outdoor_sand" / "outdoor_sand_07.png"
FINISH = "outdoor_sand"


def _load(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"))


def main() -> int:
    if not G1.is_file():
        print("missing G1 reference:", G1)
        return 1

    color_paths, color_meta = resolve_texture_reference_paths(str(G1), FINISH, purpose="scoring")
    finish_dir = G1.parent
    spatial_paths = sorted(
        str(p.resolve())
        for p in finish_dir.glob(f"{FINISH}_*.png")
        if p.stem[len(FINISH) + 1 :].isdigit()
    )
    if color_meta.get("source") != "color_invariant_swatches":
        print("Run: python scripts/crop_yili_references.py --finish-id outdoor_sand --skip-spatial")
        return 1

    g1 = _load(G1)
    color_rgbs = [_load(Path(p)) for p in color_paths]
    spatial_rgbs = [_load(Path(p)) for p in spatial_paths if Path(p).is_file()]

    print(f"color swatches: {len(color_rgbs)}  spatial refs: {len(spatial_rgbs)}")
    print(f"aggregation: {color_meta.get('aggregation')}")

    # Self-similarity sanity (g1 vs color proto should be moderate-high, not perfect)
    proto_sim = proto_reference_texture_similarity(g1, color_rgbs)
    mean_color_sim = mean_reference_texture_similarity(g1, color_rgbs, aggregation="mean_sim")
    single_sim = mean_reference_texture_similarity(g1, [g1], aggregation="mean_sim")
    print(f"G1 vs color-proto sim: {proto_sim:.4f}")
    print(f"G1 vs mean(per-color) sim: {mean_color_sim:.4f}")
    print(f"G1 vs self sim: {single_sim:.4f}")

    finish_cfg = _load_finish_cfg(FINISH)
    defaults = _defaults_from_bakecoat(finish_cfg.get("bakecoat_procedural") or {})

    ws_single, meta_single = estimate_texture_params([g1], defaults)
    ws_color, meta_color = estimate_texture_params(color_rgbs, defaults)
    print("\nwarm-start bump_strength:")
    print(f"  single G1: {ws_single['bump_strength']:.4f}")
    print(f"  14-color median: {ws_color['bump_strength']:.4f}")
    print("median_stats glcm / fft_centroid:")
    print(f"  single: {measure_reference_texture_stats(g1)['glcm_contrast']:.3f} / "
          f"{measure_reference_texture_stats(g1)['fft_centroid']:.3f}")
    print(f"  color:  {meta_color['median_stats']['glcm_contrast']:.3f} / "
          f"{meta_color['median_stats']['fft_centroid']:.3f}")

    out = _REPO / "outputs" / "yili_crops" / "outdoor_sand" / "color_scoring_compare.json"
    out.write_text(
        json.dumps(
            {
                "g1": str(G1),
                "n_color": len(color_rgbs),
                "proto_sim_g1_vs_colors": proto_sim,
                "mean_sim_g1_vs_colors": mean_color_sim,
                "warm_start_single": ws_single,
                "warm_start_color_median": ws_color,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwritten {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
