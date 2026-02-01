#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
CONFIG_PATH="${REPO_ROOT}/config.env"

# --- Load system vars from config.env ---
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "ERROR: config.env not found at $CONFIG_PATH" >&2
  exit 1
fi

# Auto-export variables defined in config.env (KEY=VALUE lines)
set -a
# shellcheck disable=SC1091
source "$CONFIG_PATH"
set +a

# --- args ---
image_type="preinstall"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)
      [[ $# -ge 2 ]] || { echo "ERROR: --type requires a value" >&2; exit 2; }
      image_type="$2"
      shift 2
      ;;
    --type=*)
      image_type="${1#*=}"
      shift
      ;;
    --) shift; break ;;
    -*) echo "ERROR: unknown option: $1" >&2; exit 2 ;;
    *) break ;;
  esac
done

case "$image_type" in
  preinstall|clean) ;;
  *) echo "ERROR: --type must be 'preinstall' or 'clean' (got: $image_type)" >&2; exit 2 ;;
esac

# --- Locate apptainer binary (APPTAINER_DIR or PATH fallback) ---
APPTAINER_BIN=""
if [[ -n "${APPTAINER_DIR-}" ]]; then
  candidate_bin="${APPTAINER_DIR%/}/apptainer"
  if [[ -x "$candidate_bin" ]]; then
    APPTAINER_BIN="${candidate_bin}"
  fi
fi
if [[ -z "${APPTAINER_BIN}" ]]; then
  apptainer_bin="$(command -v apptainer || true)"
  if [[ -z "${apptainer_bin}" ]]; then
    if [[ -n "${APPTAINER_DIR-}" ]]; then
      echo "ERROR: apptainer binary not found at ${APPTAINER_DIR%/}/apptainer and not found on PATH. Set APPTAINER_DIR in config.env." >&2
    else
      echo "ERROR: apptainer not found on PATH. Set APPTAINER_DIR in config.env." >&2
    fi
    exit 1
  fi
  APPTAINER_BIN="${apptainer_bin}"
fi
IMAGES_DIR="${REPO_ROOT}/image"
SIF_PATH="${IMAGES_DIR%/}/madagents.sif"
DEF_PATH="${IMAGES_DIR%/}/madagents_${image_type}.def"
IMG_PATH="${IMAGES_DIR%/}/mad_overlay.img"

if [[ ! -f "$DEF_PATH" ]]; then
  echo "ERROR: Definition file not found at: $DEF_PATH" >&2
  exit 1
fi

# --- Remove existing SIF if present ---
if [[ -e "$SIF_PATH" ]]; then
  echo "Found existing image at $SIF_PATH — removing it..."
  rm -f -- "$SIF_PATH"
fi

# --- Build the image ---
echo "Building image:"
echo "  $APPTAINER_BIN build \"$SIF_PATH\" \"$DEF_PATH\""
# "$APPTAINER_BIN" build --fakeroot "$SIF_PATH" "$DEF_PATH"
(
  cd "$REPO_ROOT"
  "$APPTAINER_BIN" build --fakeroot "$SIF_PATH" "$DEF_PATH"
)
echo "Done. Built: $SIF_PATH"

# --- Build the overlay ---
if [[ -f "$IMG_PATH" ]]; then
  echo "Found existing overlay at $IMG_PATH — removing it..."
  rm -f -- "$IMG_PATH"
fi

echo "Building overlay:"
echo "  $APPTAINER_BIN overlay create --fakeroot --sparse --size 10240 \"$IMG_PATH\""
"$APPTAINER_BIN" overlay create --fakeroot --sparse --size 10240 "$IMG_PATH"
# "$APPTAINER_BIN" overlay create --size 1024 "$IMG_PATH"
echo "Done. Built: $IMG_PATH"

# "$APPTAINER_BIN" cache clean"
