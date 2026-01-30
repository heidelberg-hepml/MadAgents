#!/usr/bin/env python3
"""Plot basic kinematic distributions for the EFT ttbar Delphes NPZ dataset.

This script reads an NPZ file containing Delphes-level events and produces a
small set of 1D histograms that help understand the dataset:

- Leading jet $p_T$ (weighted by event weights).
- Missing transverse energy (MET, weighted by event weights).
- Event weight distribution (unweighted counts of weight values).
- Jet multiplicity for jets with $p_T > 30$ GeV (weighted).
- Lepton (electron + muon) multiplicity with a simple $p_T > 10$ GeV cut (weighted),
  if electron/muon arrays are present.

Usage (from the dataset root, typically /output/dataset):

    python3 documentation/scripts/plot_distributions.py \
        --npz output/dataset/ufo_ttbar_reweighted.npz --max-events 5000

If --npz is omitted, the script will default to the canonical NPZ path under the
current dataset tree.
"""

import argparse
import os
from typing import Optional

import numpy as np
import matplotlib

# Use a non-interactive backend suitable for batch jobs.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot basic kinematic distributions from an EFT ttbar Delphes NPZ "
            "file (ufo_ttbar_reweighted.npz)."
        )
    )
    parser.add_argument(
        "--npz",
        type=str,
        default=None,
        help=(
            "Path to the input NPZ file. If omitted, the script tries to "
            "locate 'output/dataset/ufo_ttbar_reweighted.npz' relative to "
            "the dataset root."
        ),
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default=None,
        help=(
            "Directory in which to store the plots. If omitted, defaults to "
            "'documentation/plots' under the dataset root."
        ),
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help=(
            "Maximum number of events to use (a simple head slice). Useful "
            "for quick smoke tests. If not set, all events are used."
        ),
    )
    return parser.parse_args()


def _resolve_paths(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve default NPZ and output paths relative to the dataset tree.

    The script is expected to live in
      dataset_root/documentation/scripts/plot_distributions.py
    where dataset_root is typically /output/dataset.
    """

    script_dir = os.path.dirname(os.path.abspath(__file__))
    documentation_dir = os.path.dirname(script_dir)
    dataset_root = os.path.dirname(documentation_dir)

    if args.npz is None:
        # Canonical NPZ location from the dataset root.
        npz_path = os.path.join(dataset_root, "output", "dataset", "ufo_ttbar_reweighted.npz")
    else:
        npz_path = args.npz

    if args.outdir is None:
        outdir = os.path.join(documentation_dir, "plots")
    else:
        outdir = args.outdir

    return npz_path, outdir


def _to_1d(array: np.ndarray, n_events: Optional[int] = None) -> np.ndarray:
    """Return a flattened 1D view of the first n_events entries of array."""
    if n_events is not None:
        array = array[:n_events]
    return np.ravel(array)


def _save_hist(
    x: np.ndarray,
    weights: Optional[np.ndarray],
    bins: np.ndarray,
    xlabel: str,
    ylabel: str,
    title: str,
    out_png: str,
    out_pdf: Optional[str] = None,
    logy: bool = False,
) -> None:
    """Helper to save a 1D histogram with publication-style defaults."""
    if x.size == 0:
        print(f"[warn] No entries for histogram '{title}', skipping.")
        return

    fig, ax = plt.subplots(figsize=(6.0, 4.0))

    ax.hist(
        x,
        bins=bins,
        weights=weights,
        histtype="stepfilled",
        color="tab:blue",
        edgecolor="black",
        alpha=0.8,
    )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    if logy:
        ax.set_yscale("log")

    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    fig.savefig(out_png, dpi=200)
    if out_pdf is not None:
        fig.savefig(out_pdf)

    plt.close(fig)
    print(f"[info] Saved histogram: {out_png}")
    if out_pdf is not None:
        print(f"[info] Saved histogram: {out_pdf}")


def main() -> None:
    # Modest, publication-friendly style.
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.labelsize": 12,
            "axes.titlesize": 13,
            "legend.fontsize": 11,
        }
    )

    args = _parse_args()
    npz_path, outdir = _resolve_paths(args)

    os.makedirs(outdir, exist_ok=True)

    print(f"[info] Loading NPZ file: {npz_path}")
    if not os.path.isfile(npz_path):
        raise FileNotFoundError(f"Input NPZ file not found: {npz_path}")

    data = np.load(npz_path)

    required_keys = ["event_weight", "met", "jet_pt"]
    for key in required_keys:
        if key not in data.files:
            raise KeyError(f"Required array '{key}' not found in NPZ file.")

    n_events_total = data["event_weight"].shape[0]
    if args.max_events is not None and args.max_events > 0:
        n_events = min(args.max_events, n_events_total)
    else:
        n_events = n_events_total

    print(f"[info] Using {n_events} / {n_events_total} events")

    # 1D arrays.
    event_weight = _to_1d(data["event_weight"], n_events)
    met = _to_1d(data["met"], n_events)

    # 2D arrays for jets and leptons.
    jet_pt = np.asarray(data["jet_pt"][:n_events])

    has_ele = "ele_pt" in data.files
    has_mu = "mu_pt" in data.files

    # Leading jet pT.
    if jet_pt.ndim != 2 or jet_pt.shape[1] < 1:
        raise ValueError(
            f"Expected 'jet_pt' to have shape (N, Njets) with Njets>=1, got {jet_pt.shape}."
        )

    leading_jet_pt = jet_pt[:, 0]
    mask_positive_pt = leading_jet_pt > 0.0
    leading_jet_pt_pos = leading_jet_pt[mask_positive_pt]
    event_weight_pos = event_weight[mask_positive_pt]

    if leading_jet_pt_pos.size > 0:
        max_pt = float(np.max(leading_jet_pt_pos))
        max_pt = max(max_pt, 50.0)  # ensure a reasonable upper bound
        bins_pt = np.linspace(0.0, max_pt, 50)

        _save_hist(
            leading_jet_pt_pos,
            event_weight_pos,
            bins_pt,
            xlabel=r"$p_T^{\mathrm{jet}_1}$ [GeV]",
            ylabel=r"Events (weighted)",
            title=r"Leading jet $p_T$ distribution",
            out_png=os.path.join(outdir, "leading_jet_pt.png"),
            out_pdf=os.path.join(outdir, "leading_jet_pt.pdf"),
        )
    else:
        print("[warn] No events with positive leading jet pT; skipping leading jet plot.")

    # MET distribution.
    met_pos = met[met > 0.0]
    event_weight_met = event_weight[met > 0.0]
    if met_pos.size > 0:
        max_met = float(np.max(met_pos))
        max_met = max(max_met, 50.0)
        bins_met = np.linspace(0.0, max_met, 50)

        _save_hist(
            met_pos,
            event_weight_met,
            bins_met,
            xlabel=r"$E_T^{\mathrm{miss}}$ [GeV]",
            ylabel=r"Events (weighted)",
            title=r"Missing transverse energy distribution",
            out_png=os.path.join(outdir, "met.png"),
            out_pdf=os.path.join(outdir, "met.pdf"),
        )
    else:
        print("[warn] No events with positive MET; skipping MET plot.")

    # Event weight distribution (unweighted counts of weight values).
    if event_weight.size > 0:
        w_min = float(np.min(event_weight))
        w_max = float(np.max(event_weight))
        if w_min == w_max:
            w_min -= 0.5
            w_max += 0.5
        bins_w = np.linspace(w_min, w_max, 60)

        _save_hist(
            event_weight,
            None,
            bins_w,
            xlabel=r"Event weight",
            ylabel=r"Events",
            title=r"Event weight distribution",
            out_png=os.path.join(outdir, "event_weight.png"),
            out_pdf=os.path.join(outdir, "event_weight.pdf"),
            logy=True,
        )
    else:
        print("[warn] No event weights found; skipping weight distribution plot.")

    # Jet multiplicity for jets with pT > 30 GeV.
    jet_mult = np.sum(jet_pt > 30.0, axis=1)
    max_jmult = int(np.max(jet_mult)) if jet_mult.size > 0 else 0
    if max_jmult >= 0:
        bins_jmult = np.arange(-0.5, max_jmult + 1.5, 1.0)
        _save_hist(
            jet_mult,
            event_weight,
            bins_jmult,
            xlabel=r"$N_{\mathrm{jets}}(p_T > 30\,\mathrm{GeV})$",
            ylabel=r"Events (weighted)",
            title=r"Jet multiplicity distribution",
            out_png=os.path.join(outdir, "jet_multiplicity.png"),
            out_pdf=os.path.join(outdir, "jet_multiplicity.pdf"),
        )

    # Lepton (electron + muon) multiplicity with a simple pT cut.
    lepton_mult: Optional[np.ndarray] = None

    if has_ele:
        ele_pt = np.asarray(data["ele_pt"][:n_events])
        ele_mult = np.sum(ele_pt > 10.0, axis=1)
        lepton_mult = ele_mult if lepton_mult is None else lepton_mult + ele_mult

    if has_mu:
        mu_pt = np.asarray(data["mu_pt"][:n_events])
        mu_mult = np.sum(mu_pt > 10.0, axis=1)
        lepton_mult = mu_mult if lepton_mult is None else lepton_mult + mu_mult

    if lepton_mult is not None and lepton_mult.size > 0:
        max_lmult = int(np.max(lepton_mult))
        bins_lmult = np.arange(-0.5, max_lmult + 1.5, 1.0)

        _save_hist(
            lepton_mult,
            event_weight,
            bins_lmult,
            xlabel=r"$N_{\ell}(p_T > 10\,\mathrm{GeV})$",
            ylabel=r"Events (weighted)",
            title=r"Lepton multiplicity distribution",
            out_png=os.path.join(outdir, "lepton_multiplicity.png"),
            out_pdf=os.path.join(outdir, "lepton_multiplicity.pdf"),
        )
    else:
        print(
            "[info] No lepton arrays ('ele_pt'/'mu_pt') found or no leptons above "
            "threshold; skipping lepton multiplicity plot."
        )

    print(f"[info] All requested plots written to: {outdir}")


if __name__ == "__main__":
    main()
