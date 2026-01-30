#!/usr/bin/env bash
set -euo pipefail
PYTHONDONTWRITEBYTECODE=1

R="$(pwd)"; S="$R/scripts"; O="$R/output"; W="$O/work"; T="$W/tmp"; M="/opt/MG5_aMC/bin/mg5_aMC"
[ -x "$M" ] || { echo "missing $M"; exit 1; }
mkdir -p "$O" "$W" "$T"

LOG="$O/log.txt"
exec > >(tee -a "$LOG") 2>&1

N="${NEVENTS:-10000}"
NLO="${NEVENTS_NLO:-$N}"
LO="${NEVENTS_LO:-$N}"
UFO="${NEVENTS_UFO:-$N}"

mk(){ python3 -B - <<PY
import tempfile
print(tempfile.mkstemp(prefix="mg5_", suffix=".mg5", dir="$T")[1])
PY
}

A="$(mk)"
sed "s/__NEVENTS__/$NLO/g" "$S/mg5_sm_nlo_ttbar.mg5" >"$A"
(cd "$W" && "$M" "$A")

B="$(mk)"
sed "s/__NEVENTS__/$LO/g" "$S/mg5_sm_lo_ttbar.mg5" >"$B"
(cd "$W" && "$M" "$B")

C="$(mk)"
sed "s/__NEVENTS__/$UFO/g" "$S/mg5_ufo_parton_ttbar.mg5" >"$C"
(cd "$W" && PYTHONPATH="/opt/MG5_aMC/models/dim6top_LO_UFO:/opt/MG5_aMC/models:${PYTHONPATH:-}" "$M" "$C")

SMLO_PROC="$O/proc_sm_lo_ttbar"
SMNLO_PROC="$O/proc_sm_nlo_ttbar"
UFO_PROC="$O/proc_ufo_parton_ttbar"

fix_mg5_cfg() {
  python3 - <<'PY'
import re
from pathlib import Path

pairs = {
  "pythia8_path": "/opt/MG5_aMC/HEPTools/pythia8",
  "mg5amc_py8_interface_path": "/opt/MG5_aMC/HEPTools/MG5aMC_PY8_interface",
}

files = [
  Path("/output/dataset/output/proc_ufo_parton_ttbar/Cards/me5_configuration.txt"),
]

for f in files:
  if not f.exists():
    continue
  lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
  out, seen = [], set()
  for line in lines:
    m = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", line)
    if m and m.group(1) in pairs:
      k = m.group(1)
      out.append(f"{k} = {pairs[k]}")
      seen.add(k)
    else:
      out.append(line)
  for k,v in pairs.items():
    if k not in seen:
      out.append(f"{k} = {v}")
  f.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
}

fix_mg5_cfg

UFO_LHE_ORIG="$UFO_PROC/Events/ufo_parton/unweighted_events.lhe.gz"
UFO_LHE_RW="$UFO_PROC/Events/ufo_parton/events_reweighted.lhe.gz"
CSV="$O/ufo_event_weights.csv"
KJ="$O/kfactors_mtt.json"

python3 -B "$S/build_kfactor_mtt.py" \
  --nlo-proc "$SMNLO_PROC" --nlo-run sm_nlo \
  --lo-proc "$SMLO_PROC"  --lo-run  sm_lo \
  --out "$KJ" --nbins 60 --mmin 340 --mmax 2000

python3 -B "$S/apply_kfactor_to_lhe.py" \
  --in-lhe "$UFO_LHE_ORIG" --kjson "$KJ" \
  --out-lhe "$UFO_LHE_RW" --out-csv "$CSV"

cp -f "$UFO_LHE_RW" "$UFO_LHE_ORIG"

UFO_CARDS="$UFO_PROC/Cards"
mkdir -p "$UFO_CARDS"

DEL_SRC="$(ls -1 /opt/MG5_aMC/Template/Cards/delphes_card*.dat 2>/dev/null | head -n1 || true)"
if [ -z "${DEL_SRC:-}" ]; then
  DEL_SRC="$(ls -1 /opt/MG5_aMC/Template/Common/Cards/delphes_card*.dat 2>/dev/null | head -n1 || true)"
fi
if [ -z "${DEL_SRC:-}" ]; then
  echo "ERROR: Could not find a Delphes card under /opt/MG5_aMC/Template/Cards/ or /opt/MG5_aMC/Template/Common/Cards/ (delphes_card*.dat)"
  exit 1
fi
cp -f "$DEL_SRC" "$O/proc_ufo_parton_ttbar/Cards/delphes_card.dat"

echo "Using Delphes card: $DEL_SRC -> $UFO_CARDS/delphes_card.dat"

(cd "$UFO_PROC" && printf "shower pythia8 ufo_parton -f\ndelphes ufo_parton -f\nexit\n" | ./bin/madevent)

D="$O/dataset"
mkdir -p "$D"
cp -f "$KJ"  "$D/kfactors_mtt.json"
cp -f "$CSV" "$D/ufo_event_weights.csv"

UFO_ROOT="$(ls -1 "$UFO_PROC/Events/ufo_parton"/tag_*_delphes*.root 2>/dev/null | head -n 1 || true)"
if [ -z "$UFO_ROOT" ]; then
  echo "ERROR: No Delphes ROOT found under $UFO_PROC/Events/ufo_parton/"
  echo "Files present:"
  ls -la "$UFO_PROC/Events/ufo_parton/" || true
  exit 1
fi

cp -f "$UFO_ROOT" "$D/ufo_ttbar_reweighted_delphes.root"

python3 -B "$S/delphes_to_npz.py" \
  --in-root "$UFO_ROOT" \
  --out-npz "$D/ufo_ttbar_reweighted.npz" \
  --max-jets 10 --max-ele 4 --max-mu 4

printf "%s\n" "done:$D"
