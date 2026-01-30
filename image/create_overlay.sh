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
IMG_PATH="${IMAGES_DIR%/}/mad_overlay.img"

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
