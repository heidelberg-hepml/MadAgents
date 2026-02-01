#!/usr/bin/env python

import os
import math
import numpy as np
import pyhepmc
import pyjet

HEPMC_DIR = '/workspace/heptapod/analysis/hepmc'
MASS_POINTS = [1000, 1500, 2000]

# Object selection thresholds (GeV)
ELE_PT_MIN = 50.0
ELE_ETA_MAX = 2.5
JET_PT_MIN = 50.0
JET_ETA_MAX = 5.0

# Histogram binning: 0–2500 GeV in 50 GeV bins
BIN_MIN = 0.0
BIN_MAX = 2500.0
BIN_WIDTH = 50.0
BINS = np.arange(BIN_MIN, BIN_MAX + BIN_WIDTH, BIN_WIDTH, dtype=float)
BIN_CENTERS = 0.5 * (BINS[:-1] + BINS[1:])


def four_momentum_from_particle(p):
    """Return (E, px, py, pz) from a pyhepmc GenParticle."""
    m = p.momentum
    return float(m.e), float(m.px), float(m.py), float(m.pz)


def kinematics_from_Epxpypz(E, px, py, pz):
    """Compute (pt, eta, phi) from cartesian components."""
    pt = math.hypot(px, py)
    p = math.sqrt(px * px + py * py + pz * pz)
    # Pseudorapidity; guard against division issues
    if p > 0.0 and abs(pz) < p:
        cos_theta = pz / p
        cos_theta = max(-1.0, min(1.0, cos_theta))
        theta = math.acos(cos_theta)
        eta = -math.log(math.tan(0.5 * theta))
    else:
        if pz > 0:
            eta = float('inf')
        elif pz < 0:
            eta = -float('inf')
        else:
            eta = 0.0
    phi = math.atan2(py, px)
    return pt, eta, phi


def invariant_mass(ev1, ev2):
    """Invariant mass of two four-vectors v=(E,px,py,pz)."""
    E = ev1[0] + ev2[0]
    px = ev1[1] + ev2[1]
    py = ev1[2] + ev2[2]
    pz = ev1[3] + ev2[3]
    m2 = E * E - (px * px + py * py + pz * pz)
    return math.sqrt(m2) if m2 > 0.0 else 0.0


def analyze_mass_point(mass):
    """Process one mass point and return m_LQ^min array, counters, and histogram info."""
    path = os.path.join(HEPMC_DIR, f's1_m{mass}.hepmc')
    if not os.path.isfile(path):
        print(f'[WARN] HepMC file not found for mass {mass} GeV: {path}')
        return np.array([], dtype=float), 0, 0

    m_vals = []
    n_events = 0
    n_selected = 0

    # Use pyhepmc.open to automatically pick the correct HepMC2 reader.
    f = pyhepmc.open(path)
    try:
        for event in f:
            n_events += 1

            # Final-state particles: use status == 1 (HepMC2/Pythia8 convention).
            final_particles = [p for p in event.particles if p.status == 1]

            electrons = []  # store dicts with 4-v and kinematics
            jet_inputs = []  # list of (pT, eta, phi, mass) for pyjet

            for p in final_particles:
                pid = p.pid
                # Classify neutrinos (exclude from jets and leptons)
                if abs(pid) in (12, 14, 16):
                    continue

                E, px, py, pz = four_momentum_from_particle(p)
                pt, eta, phi = kinematics_from_Epxpypz(E, px, py, pz)

                # Electrons
                if abs(pid) == 11:
                    electrons.append({
                        'E': E,
                        'px': px,
                        'py': py,
                        'pz': pz,
                        'pt': pt,
                        'eta': eta,
                        'phi': phi,
                    })
                else:
                    # All other visible stable particles go into jets
                    jet_inputs.append((pt, eta, phi, 0.0))  # massless approximation

            # Electron selection
            selected_e = [e for e in electrons if e['pt'] > ELE_PT_MIN and abs(e['eta']) < ELE_ETA_MAX]
            if len(selected_e) != 2:
                continue

            # Jet clustering
            if not jet_inputs:
                continue

            particles_array = np.array(jet_inputs, dtype=[('pT', 'f8'), ('eta', 'f8'), ('phi', 'f8'), ('mass', 'f8')])
            sequence = pyjet.cluster(particles_array, R=0.4, p=-1)  # anti-kT
            jets = sequence.inclusive_jets(ptmin=JET_PT_MIN)
            jets = [j for j in jets if abs(j.eta) < JET_ETA_MAX]

            if len(jets) < 2:
                continue

            # Sort jets by pT and take the two leading
            jets.sort(key=lambda j: j.pt, reverse=True)
            j1, j2 = jets[0], jets[1]

            # Build four-vectors for electrons (sorted by pT for definiteness)
            selected_e.sort(key=lambda e: e['pt'], reverse=True)
            l1, l2 = selected_e[0], selected_e[1]

            v_l1 = (l1['E'], l1['px'], l1['py'], l1['pz'])
            v_l2 = (l2['E'], l2['px'], l2['py'], l2['pz'])
            v_j1 = (j1.e, j1.px, j1.py, j1.pz)
            v_j2 = (j2.e, j2.px, j2.py, j2.pz)

            # Two possible pairings
            mA1 = invariant_mass(v_l1, v_j1)
            mA2 = invariant_mass(v_l2, v_j2)
            mB1 = invariant_mass(v_l1, v_j2)
            mB2 = invariant_mass(v_l2, v_j1)

            diffA = abs(mA1 - mA2)
            diffB = abs(mB1 - mB2)

            if diffA <= diffB:
                m1, m2 = mA1, mA2
            else:
                m1, m2 = mB1, mB2

            m_lq_min = min(m1, m2)
            m_vals.append(m_lq_min)
            n_selected += 1
    finally:
        f.close()

    m_vals = np.asarray(m_vals, dtype=float)
    print(f'[INFO] Mass {mass} GeV: total events = {n_events}, selected = {n_selected}, m_LQ^min entries = {len(m_vals)}')
    return m_vals, n_events, n_selected


def main():
    all_m_vals = {}
    total_events = {}
    selected_events = {}

    for mass in MASS_POINTS:
        vals, n_evt, n_sel = analyze_mass_point(mass)
        all_m_vals[mass] = vals
        total_events[mass] = n_evt
        selected_events[mass] = n_sel

    # Build histograms
    hist_counts = {}
    hist_norm = {}

    for mass in MASS_POINTS:
        vals = all_m_vals.get(mass, np.array([], dtype=float))
        if vals.size == 0:
            counts = np.zeros(len(BINS) - 1, dtype=float)
            norm = counts.copy()
        else:
            counts, _ = np.histogram(vals, bins=BINS)
            total = float(counts.sum())
            if total > 0.0:
                norm = counts / total
            else:
                norm = np.zeros_like(counts, dtype=float)
        hist_counts[mass] = counts
        hist_norm[mass] = norm

    # Save to NPZ for plotter agent
    out_path = os.path.join(os.path.dirname(__file__), 'mLQmin_histograms.npz')
    np.savez(
        out_path,
        bins=BINS,
        bin_centers=BIN_CENTERS,
        m1000_counts=hist_counts.get(1000),
        m1500_counts=hist_counts.get(1500),
        m2000_counts=hist_counts.get(2000),
        m1000_norm=hist_norm.get(1000),
        m1500_norm=hist_norm.get(1500),
        m2000_norm=hist_norm.get(2000),
        total_events_1000=total_events.get(1000, 0),
        total_events_1500=total_events.get(1500, 0),
        total_events_2000=total_events.get(2000, 0),
        selected_events_1000=selected_events.get(1000, 0),
        selected_events_1500=selected_events.get(1500, 0),
        selected_events_2000=selected_events.get(2000, 0),
    )

    print(f'[INFO] Saved histograms to {out_path}')

    # Print basic distribution summaries
    for mass in MASS_POINTS:
        vals = all_m_vals.get(mass, np.array([], dtype=float))
        if vals.size == 0:
            print(f'[SUMMARY] Mass {mass} GeV: no events passed selection.')
            continue
        counts = hist_counts[mass]
        if counts.sum() > 0:
            peak_bin = int(np.argmax(counts))
            peak_center = BIN_CENTERS[peak_bin]
        else:
            peak_center = float('nan')
        mean_val = float(vals.mean()) if vals.size > 0 else float('nan')
        print(f'[SUMMARY] Mass {mass} GeV: selected events = {selected_events[mass]}, '
              f'm_LQ^min mean ~ {mean_val:.1f} GeV, peak around bin center ~ {peak_center:.1f} GeV')


if __name__ == '__main__':
    main()
