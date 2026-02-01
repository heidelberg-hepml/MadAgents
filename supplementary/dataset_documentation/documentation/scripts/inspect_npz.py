#!/usr/bin/env python3
"""Inspect a NPZ file produced by delphes_to_npz.py.

Usage:
  python inspect_npz.py [--npz PATH]

Default PATH is /output/dataset/output/dataset/ufo_ttbar_reweighted.npz.

The script is read-only with respect to the dataset. It prints, for each
array in the NPZ:
  * key name
  * shape
  * dtype
  * basic statistics for numeric arrays (min, max, mean)
  * a short summary of unique values for small-discrete arrays
"""

import argparse
import sys
from pathlib import Path

import numpy as np


def format_shape(shape):
    return "(" + ", ".join(str(int(x)) for x in shape) + ")"


def summarize_array(name: str, arr: np.ndarray) -> None:
    print(f"key={name}")
    print(f"  shape={format_shape(arr.shape)} dtype={arr.dtype}")

    if arr.size == 0:
        print("  note: empty array")
        return

    if np.issubdtype(arr.dtype, np.number):
        # Use nan-aware stats to be robust.
        with np.errstate(all="ignore"):
            amin = np.nanmin(arr)
            amax = np.nanmax(arr)
            mean = np.nanmean(arr)
        print(f"  stats: min={float(amin):.6g} max={float(amax):.6g} mean={float(mean):.6g}")

        # Try to detect small discrete sets (e.g. charges, b-tags).
        flat = arr.ravel()
        # For large arrays, subsample to keep runtime reasonable.
        if flat.size > 200000:
            flat = flat[:: max(1, flat.size // 200000)]
        uniq = np.unique(flat)
        if uniq.size <= 20:
            # For discrete-like arrays, also print counts.
            vals, counts = np.unique(flat, return_counts=True)
            pairs = ", ".join(f"{v}:{c}" for v, c in zip(vals, counts))
            print(f"  unique_values ({len(vals)}): {pairs}")
        else:
            print(f"  unique_values: {uniq.size} distinct (not listed)")
    else:
        print("  note: non-numeric dtype, stats not computed")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--npz",
        default="/output/dataset/output/dataset/ufo_ttbar_reweighted.npz",
        help="Path to NPZ file to inspect",
    )
    args = p.parse_args(argv)

    path = Path(args.npz)
    if not path.is_file():
        print(f"ERROR: NPZ file not found: {path}", file=sys.stderr)
        return 1

    print(f"NPZ path: {path}")

    with np.load(path, allow_pickle=False) as data:
        keys = sorted(data.files)
        print("keys:")
        for k in keys:
            print(f"  {k}")

        # Infer number of events from a canonical 1D array if available.
        n_events = None
        for cand in ("event_weight", "jet_pt", "met"):
            if cand in data:
                arr = data[cand]
                if arr.ndim >= 1:
                    n_events = int(arr.shape[0])
                    break
        if n_events is not None:
            print(f"n_events: {n_events}")

        print("\nfield_summaries:")
        for k in keys:
            arr = data[k]
            summarize_array(k, arr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
