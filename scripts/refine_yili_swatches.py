#!/usr/bin/env python3
"""Re-run swatch refinement on existing yili_crops/<finish_id>/ folder.

Usage:
    python scripts/refine_yili_swatches.py --finish-id outdoor_sand
    python scripts/refine_yili_swatches.py --finish-id outdoor_sand --reject-fraction 0.3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from yili_swatch_refine import (
    finish_out_dir,
    load_swatches_from_dir,
    refine_swatches,
    save_refine_outputs,
)

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "outputs" / "yili_crops"


def main() -> int:
    p = argparse.ArgumentParser(description="Refine Yili swatch crops by quality + texture consensus")
    p.add_argument("--finish-id", required=True)
    p.add_argument("--out-dir", type=Path, default=OUT_DIR)
    p.add_argument("--reject-fraction", type=float, default=0.3, help="Drop worst fraction in phase 1")
    p.add_argument("--mad-factor", type=float, default=2.5, help="MAD multiplier for outlier cutoff")
    args = p.parse_args()

    finish_dir = finish_out_dir(args.out_dir.resolve(), args.finish_id)
    if not finish_dir.is_dir():
        print(f"ERROR: not found: {finish_dir}")
        return 1

    items = load_swatches_from_dir(finish_dir, args.finish_id)
    if not items:
        print(f"ERROR: no swatch images in {finish_dir}")
        return 1

    result = refine_swatches(
        items,
        reject_fraction=args.reject_fraction,
        outlier_mad_factor=args.mad_factor,
    )
    report = save_refine_outputs(result, finish_dir, args.finish_id, all_items=items)

    print(f"Input: {len(items)}  selected: {len(result.selected)}")
    print(f"  rejected brightness: {[it.index for it in result.rejected_brightness]}")
    print(f"  rejected glare: {[it.index for it in result.rejected_glare]}")
    print(f"  rejected quality (30%): {[it.index for it in result.rejected_quality]}")
    print(f"  rejected outlier: {[it.index for it in result.rejected_outlier]}")
    print(f"  medoid index: {result.medoid_index}")
    print(f"  -> {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
