#!/usr/bin/env python3
"""Plot m_LQ^min resonance distributions for scalar leptoquark benchmarks.

This script loads precomputed histograms for the reconstructed
$m_{\mathrm{LQ}}^{\min}$ observable from
"/workspace/heptapod/analysis/mLQmin_histograms.npz" and produces a
publication-style comparison plot for three benchmark masses
($m_{\mathrm{S1}} = 1000, 1500, 2000$ GeV).

The main output is a single panel overlay of the three unit-area-normalized
distributions, including Poisson uncertainties derived from the raw
histogram counts. The plot is saved as both PNG and PDF to
"/output/heptapod/plots".

Usage (from /workspace/heptapod/analysis):

    source /workspace/heptapod/env_setup.sh
    python plot_mLQmin.py

"""

from __future__ import annotations

import os
from typing import Tuple

import numpy as np
import matplotlib.pyplot as plt


INPUT_NPZ = "/workspace/heptapod/analysis/mLQmin_histograms.npz"
OUTPUT_DIR = "/output/heptapod/plots"


def _compute_normalized_yields(
    bins: np.ndarray, counts: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Return unit-area normalized yields and uncertainties.

    Parameters
    ----------
    bins : np.ndarray
        Bin edges array of length N+1.
    counts : np.ndarray
        Raw counts per bin of length N.

    Returns
    -------
    norm : np.ndarray
        Normalized yield per bin, interpreted as a probability density
        such that the integral over $m_{\mathrm{LQ}}^{\min}$ equals 1.
    norm_err : np.ndarray
        Poisson uncertainties on the normalized yields.
    """

    bins = np.asarray(bins, dtype=float)
    counts = np.asarray(counts, dtype=float)

    if bins.ndim != 1 or counts.ndim != 1:
        raise ValueError("bins and counts must be 1D arrays")
    if len(bins) != len(counts) + 1:
        raise ValueError("len(bins) must be len(counts) + 1")

    bin_widths = np.diff(bins)
    total_counts = counts.sum()
    if total_counts <= 0.0:
        raise ValueError("Total counts must be positive to normalize histogram")

    # Probability density: (1 / total_counts) * (counts / bin_width)
    norm = counts / (total_counts * bin_widths)

    # Poisson uncertainties on counts: sqrt(N), propagated to the density.
    counts_err = np.sqrt(counts)
    norm_err = counts_err / (total_counts * bin_widths)

    return norm, norm_err


def _make_step_line(bins: np.ndarray, values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Construct step-style line coordinates from bin edges and bin values.

    This converts a histogram specified by bin edges and bin contents into
    a pair of (x, y) arrays suitable for `plt.plot`, with explicit vertical
    edges between bins so that the binning is visually clear.
    """

    bins = np.asarray(bins, dtype=float)
    values = np.asarray(values, dtype=float)

    if len(bins) != len(values) + 1:
        raise ValueError("len(bins) must be len(values) + 1")

    # Repeat each edge and each value to form a step function.
    x = np.repeat(bins, 2)[1:-1]
    y = np.repeat(values, 2)
    return x, y


def plot_mLQmin_comparison(
    npz_path: str = INPUT_NPZ,
    output_dir: str = OUTPUT_DIR,
) -> None:
    """Create the m_LQ^min comparison plot for three benchmark masses.

    The function loads the NPZ file, recomputes unit-area normalized yields
    and uncertainties from the raw counts, and produces a single overlay
    plot with three resonance shapes.
    """

    if not os.path.exists(npz_path):
        raise FileNotFoundError(f"Input NPZ file not found: {npz_path}")

    os.makedirs(output_dir, exist_ok=True)

    data = np.load(npz_path)
    bins = data["bins"]
    bin_centers = data["bin_centers"]

    m1000_counts = data["m1000_counts"]
    m1500_counts = data["m1500_counts"]
    m2000_counts = data["m2000_counts"]

    # Recompute normalized yields and uncertainties from the raw counts.
    m1000_norm, m1000_err = _compute_normalized_yields(bins, m1000_counts)
    m1500_norm, m1500_err = _compute_normalized_yields(bins, m1500_counts)
    m2000_norm, m2000_err = _compute_normalized_yields(bins, m2000_counts)

    # Configure a publication-style matplotlib setup.
    plt.style.use("default")
    plt.rcParams.update(
        {
            "font.size": 14,
            "axes.labelsize": 16,
            "axes.titlesize": 16,
            "legend.fontsize": 12,
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
            "figure.figsize": (7.0, 5.0),
            "axes.grid": True,
            "grid.alpha": 0.3,
        }
    )

    fig, ax = plt.subplots()

    # Build step-style lines so that the binning is apparent.
    x1000, y1000 = _make_step_line(bins, m1000_norm)
    x1500, y1500 = _make_step_line(bins, m1500_norm)
    x2000, y2000 = _make_step_line(bins, m2000_norm)

    ax.plot(x1000, y1000, color="tab:blue", linestyle="-", linewidth=1.8, label=r"$m_{\mathrm{S1}} = 1000\,\mathrm{GeV}$")
    ax.plot(x1500, y1500, color="tab:orange", linestyle="--", linewidth=1.8, label=r"$m_{\mathrm{S1}} = 1500\,\mathrm{GeV}$")
    ax.plot(x2000, y2000, color="tab:green", linestyle=":", linewidth=1.8, label=r"$m_{\mathrm{S1}} = 2000\,\mathrm{GeV}$")

    # Overlay statistical uncertainties as error bars at the bin centers.
    ax.errorbar(
        bin_centers,
        m1000_norm,
        yerr=m1000_err,
        fmt="o",
        color="tab:blue",
        markersize=3,
        linewidth=0.8,
        capsize=2,
        alpha=0.8,
    )
    ax.errorbar(
        bin_centers,
        m1500_norm,
        yerr=m1500_err,
        fmt="s",
        color="tab:orange",
        markersize=3,
        linewidth=0.8,
        capsize=2,
        alpha=0.8,
    )
    ax.errorbar(
        bin_centers,
        m2000_norm,
        yerr=m2000_err,
        fmt="^",
        color="tab:green",
        markersize=3,
        linewidth=0.8,
        capsize=2,
        alpha=0.8,
    )

    ax.set_xlabel(r"$m_{\mathrm{LQ}}^{\min}$ [GeV]")
    ax.set_ylabel(r"Normalized yield $(1/\mathrm{GeV})$")
    ax.set_title(r"Reconstructed $m_{\mathrm{LQ}}^{\min}$ distribution")

    ax.set_xlim(0.0, 2500.0)

    # Choose a sensible y-range with a small headroom above the tallest peak.
    ymax = max(
        float(m1000_norm.max()), float(m1500_norm.max()), float(m2000_norm.max())
    )
    ax.set_ylim(0.0, 1.15 * ymax)

    ax.legend(loc="best")
    fig.tight_layout()

    png_path = os.path.join(output_dir, "heptapod_mLQmin_comparison.png")
    pdf_path = os.path.join(output_dir, "heptapod_mLQmin_comparison.pdf")

    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)

    print(f"Saved comparison plot to: {png_path}")
    print(f"Saved comparison plot to: {pdf_path}")

    plt.close(fig)


def main() -> None:
    """Entry point when running as a script."""

    plot_mLQmin_comparison()


if __name__ == "__main__":
    main()