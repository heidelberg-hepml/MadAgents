#!/usr/bin/env python3
import argparse, bisect, gzip, io, json, os, sys
from typing import Dict, List, Tuple, Optional

def eprint(*a, **k):
    print(*a, file=sys.stderr, **k)

def open_text(path: str):
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "rt", encoding="utf-8", errors="replace")

def find_lhe(proc_dir: str, run: str, prefer_unweighted: bool) -> str:
    evdir = os.path.join(proc_dir, "Events", run)
    cand = []
    if prefer_unweighted:
        cand += ["unweighted_events.lhe.gz", "unweighted_events.lhe", "events.lhe.gz", "events.lhe"]
    else:
        cand += ["events.lhe.gz", "events.lhe", "unweighted_events.lhe.gz", "unweighted_events.lhe"]
    for fn in cand:
        p = os.path.join(evdir, fn)
        if os.path.isfile(p) and os.path.getsize(p) > 0:
            return p
    raise FileNotFoundError(f"Could not find a non-empty LHE in {evdir} (tried {cand})")

def parse_event_blocks(lhe_path: str):
    with open_text(lhe_path) as f:
        in_event = False
        buf = []
        for line in f:
            if not in_event:
                if line.lstrip().startswith("<event"):
                    in_event = True
                    buf = [line]
                continue
            else:
                buf.append(line)
                if line.lstrip().startswith("</event"):
                    yield buf
                    in_event = False
                    buf = []

def mtt_from_event_lines(ev_lines: List[str]) -> Optional[float]:
    header_idx = None
    for i in range(1, len(ev_lines)):
        s = ev_lines[i].strip()
        if not s or s.startswith("<"):
            continue
        header_idx = i
        break
    if header_idx is None:
        return None

    parts = ev_lines[header_idx].split()
    if len(parts) < 1:
        return None
    try:
        nup = int(float(parts[0]))
    except Exception:
        return None

    tops = []
    for j in range(header_idx + 1, min(header_idx + 1 + nup, len(ev_lines))):
        s = ev_lines[j].strip()
        if not s or s.startswith("<"):
            continue
        cols = s.split()
        if len(cols) < 10:
            continue
        try:
            pid = int(cols[0])
            status = int(cols[1])
        except Exception:
            continue
        if abs(pid) != 6:
            continue
        if status not in (1, 2):
            continue
        try:
            px, py, pz, E = map(float, cols[6:10])
        except Exception:
            continue
        tops.append((px, py, pz, E))
        if len(tops) >= 2:
            break

    if len(tops) < 2:
        return None

    (px1, py1, pz1, E1), (px2, py2, pz2, E2) = tops[0], tops[1]
    px = px1 + px2
    py = py1 + py2
    pz = pz1 + pz2
    E  = E1  + E2
    m2 = E*E - (px*px + py*py + pz*pz)
    if m2 <= 0:
        return None
    return m2 ** 0.5

def make_edges(mmin: float, mmax: float, nbins: int) -> List[float]:
    step = (mmax - mmin) / nbins
    return [mmin + i*step for i in range(nbins+1)]

def fill_hist(lhe_path: str, edges: List[float], max_events: int) -> Tuple[List[int], int, int]:
    nb = len(edges) - 1
    counts = [0] * nb
    seen = 0
    used = 0

    for ev in parse_event_blocks(lhe_path):
        seen += 1
        if max_events and seen > max_events:
            break
        mtt = mtt_from_event_lines(ev)
        if mtt is None:
            continue
        if mtt < edges[0] or mtt >= edges[-1]:
            continue
        i = bisect.bisect_right(edges, mtt) - 1
        if 0 <= i < nb:
            counts[i] += 1
            used += 1

    return counts, seen, used

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo-proc",  default="", help="LO process dir (proc_sm_lo_ttbar)")
    ap.add_argument("--lo-run",   default="", help="LO run name (sm_lo)")
    ap.add_argument("--nlo-proc", default="", help="NLO process dir (proc_sm_nlo_ttbar)")
    ap.add_argument("--nlo-run",  default="", help="NLO run name (sm_nlo)")
    ap.add_argument("--mmin", type=float, default=340.0)
    ap.add_argument("--mmax", type=float, default=2000.0)
    ap.add_argument("--nbins", type=int, default=60)
    ap.add_argument("--max-events", type=int, default=0, help="0 means no limit")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if not (a.lo_proc and a.lo_run and a.nlo_proc and a.nlo_run):
        raise SystemExit("ERROR: must provide --lo-proc/--lo-run and --nlo-proc/--nlo-run")

    edges = make_edges(a.mmin, a.mmax, a.nbins)

    lo_lhe  = find_lhe(a.lo_proc,  a.lo_run,  prefer_unweighted=True)
    nlo_lhe = find_lhe(a.nlo_proc, a.nlo_run, prefer_unweighted=False)

    eprint(f"LO LHE : {lo_lhe}")
    eprint(f"NLO LHE: {nlo_lhe}")

    lo_counts, lo_seen, lo_used   = fill_hist(lo_lhe,  edges, a.max_events)
    nlo_counts, nlo_seen, nlo_used = fill_hist(nlo_lhe, edges, a.max_events)

    eprint(f"LO events seen/used : {lo_seen}/{lo_used}")
    eprint(f"NLO events seen/used: {nlo_seen}/{nlo_used}")

    k = []
    for i in range(a.nbins):
        lo = lo_counts[i]
        nlo = nlo_counts[i]
        if lo > 0:
            k.append(nlo / lo)
        else:
            k.append(1.0)

    payload: Dict[str, object] = {
        "mmin": a.mmin,
        "mmax": a.mmax,
        "nbins": a.nbins,
        "edges": edges,
        "kfactor": k,
        "lo": {
            "proc": a.lo_proc,
            "run": a.lo_run,
            "lhe": lo_lhe,
            "seen": lo_seen,
            "used": lo_used,
            "counts": lo_counts,
        },
        "nlo": {
            "proc": a.nlo_proc,
            "run": a.nlo_run,
            "lhe": nlo_lhe,
            "seen": nlo_seen,
            "used": nlo_used,
            "counts": nlo_counts,
        },
    }

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    eprint(f"Wrote: {a.out}")

if __name__ == "__main__":
    main()
