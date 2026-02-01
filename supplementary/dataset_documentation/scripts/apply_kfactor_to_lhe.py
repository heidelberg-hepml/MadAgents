#!/usr/bin/env python3
import argparse, gzip, json, math, os
from typing import Dict, List, Tuple, Any, Optional

def open_text_in(path: str):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") \
        else open(path, "rt", encoding="utf-8", errors="replace")

def open_text_out(path: str):
    return gzip.open(path, "wt", encoding="utf-8") if path.endswith(".gz") \
        else open(path, "wt", encoding="utf-8")

def inv_mass(p: Tuple[float,float,float,float]) -> float:
    E, px, py, pz = p
    m2 = E*E - (px*px + py*py + pz*pz)
    return math.sqrt(m2) if m2 > 0 else 0.0

def parse_particle_line(line: str):
    parts = line.strip().split()
    if len(parts) < 10:
        return None
    try:
        pid = int(parts[0])
        px = float(parts[6]); py = float(parts[7]); pz = float(parts[8]); E = float(parts[9])
        return pid, (E, px, py, pz)
    except Exception:
        return None

def _maybe_unwrap_mtt(obj: Any) -> Any:
    if isinstance(obj, dict) and "mtt" in obj and isinstance(obj["mtt"], (dict, list)):
        return obj["mtt"]
    return obj

def normalize_kmap(kmap: Any) -> Tuple[List[float], List[float]]:
    kmap = _maybe_unwrap_mtt(kmap)

    if isinstance(kmap, dict) and "bins" in kmap and isinstance(kmap["bins"], list) and kmap["bins"]:
        bins = kmap["bins"]
        edges = [float(bins[0]["lo"])]
        kvals = []
        for b in bins:
            lo = float(b["lo"]); hi = float(b["hi"]); kk = float(b["k"])
            if abs(lo - edges[-1]) > 1e-12:
                edges.append(lo)
            kvals.append(kk)
            edges.append(hi)
        if len(edges) != len(kvals) + 1:
            edges = [float(b["lo"]) for b in bins] + [float(bins[-1]["hi"])]
        return edges, kvals

    def get_any(d: dict, keys: List[str]) -> Optional[Any]:
        for k in keys:
            if k in d:
                return d[k]
        return None

    if isinstance(kmap, dict):
        edges = get_any(kmap, ["edges", "bin_edges", "mtt_edges", "xedges", "x_edges"])
        kvals = get_any(kmap, ["k", "kfactors", "k_factors", "kfactor", "k_factors_mtt", "kvals"])
        if edges is not None and kvals is not None:
            edges = [float(x) for x in edges]
            kvals = [float(x) for x in kvals]
            if len(edges) == len(kvals) + 1:
                return edges, kvals

        mmin = get_any(kmap, ["mmin", "xmin", "min", "mtt_min"])
        mmax = get_any(kmap, ["mmax", "xmax", "max", "mtt_max"])
        nbins = get_any(kmap, ["nbins", "n_bins", "bins_n", "N", "mtt_nbins"])
        kvals2 = get_any(kmap, ["k", "kfactors", "k_factors", "kfactor", "k_factors_mtt", "kvals"])
        if (mmin is not None) and (mmax is not None) and (nbins is not None) and (kvals2 is not None):
            mmin = float(mmin); mmax = float(mmax); nbins = int(nbins)
            kvals2 = [float(x) for x in kvals2]
            if len(kvals2) == nbins:
                step = (mmax - mmin) / nbins
                edges = [mmin + i*step for i in range(nbins+1)]
                return edges, kvals2

    raise ValueError(
        "kjson format not recognized. Top-level keys were: "
        + (", ".join(sorted(kmap.keys())) if isinstance(kmap, dict) else f"type={type(kmap)}")
    )

def pick_kfactor(edges: List[float], kvals: List[float], mtt: float) -> float:
    if not math.isfinite(mtt):
        return 1.0
    if mtt < edges[0]:
        return kvals[0]
    if mtt >= edges[-1]:
        return kvals[-1]
    for i in range(len(kvals)):
        if edges[i] <= mtt < edges[i+1]:
            return kvals[i]
    return kvals[-1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-lhe", required=True)
    ap.add_argument("--kjson", required=True)
    ap.add_argument("--out-lhe", required=True)
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--max-events", type=int, default=10**18)
    args = ap.parse_args()

    if not os.path.exists(args.in_lhe):
        raise FileNotFoundError(args.in_lhe)
    if not os.path.exists(args.kjson):
        raise FileNotFoundError(args.kjson)

    with open(args.kjson, "r", encoding="utf-8") as f:
        kmap = json.load(f)

    edges, kvals = normalize_kmap(kmap)

    n_total = 0
    n_scaled = 0

    with open_text_in(args.in_lhe) as fin, open_text_out(args.out_lhe) as fout, open(args.out_csv, "w", encoding="utf-8") as csv:
        csv.write("ievt,mtt,kfactor,old_wgt,new_wgt\n")

        in_event = False
        for line in fin:
            if n_total >= args.max_events and not in_event:
                fout.write(line)
                continue

            if line.lstrip().startswith("<event"):
                in_event = True
                fout.write(line)
                header = next(fin)
                header_parts = header.strip().split()
                if len(header_parts) < 3:
                    fout.write(header)
                    in_event = False
                    continue

                try:
                    nup = int(header_parts[0])
                    old_wgt = float(header_parts[2])
                except Exception:
                    fout.write(header)
                    in_event = False
                    continue

                particle_lines: List[str] = []
                tops: List[Tuple[float,float,float,float]] = []
                antitops: List[Tuple[float,float,float,float]] = []

                for _ in range(nup):
                    pl = next(fin)
                    particle_lines.append(pl)
                    parsed = parse_particle_line(pl)
                    if parsed is None:
                        continue
                    pid, p4 = parsed
                    if pid == 6:
                        tops.append(p4)
                    elif pid == -6:
                        antitops.append(p4)

                tail_lines: List[str] = []
                while True:
                    tl = next(fin)
                    tail_lines.append(tl)
                    if tl.lstrip().startswith("</event"):
                        break

                mtt = float("nan")
                kfac = 1.0
                new_wgt = old_wgt
                if tops and antitops:
                    t = tops[0]; tb = antitops[0]
                    p_tt = (t[0]+tb[0], t[1]+tb[1], t[2]+tb[2], t[3]+tb[3])
                    mtt = inv_mass(p_tt)
                    kfac = pick_kfactor(edges, kvals, mtt)
                    new_wgt = old_wgt * kfac
                    n_scaled += 1

                header_parts[2] = f"{new_wgt:.16e}"
                fout.write(" ".join(header_parts) + "\n")
                for pl in particle_lines:
                    fout.write(pl)
                for tl in tail_lines:
                    fout.write(tl)

                csv.write(f"{n_total},{mtt},{kfac},{old_wgt},{new_wgt}\n")
                n_total += 1
                in_event = False
                continue

            fout.write(line)

    print(f"Scaled {n_scaled}/{n_total} events.")
    print(f"Wrote LHE: {args.out_lhe}")
    print(f"Wrote CSV: {args.out_csv}")

if __name__ == "__main__":
    main()
