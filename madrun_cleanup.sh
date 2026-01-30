#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root from this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${SCRIPT_DIR}/config.env"

# --- Load system vars from config.env ---
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "ERROR: config.env not found at $CONFIG_PATH" >&2
  exit 1
fi

set -a
. "$CONFIG_PATH"
set +a

usage() {
  cat <<'USAGE'
Usage: stop_madrun.sh [options]

Options:
      --run_dir DIR           Run directory (defaults to repo run_dir)
      --instance_name NAME    Apptainer instance name to stop
  -h, --help                  Show this help and exit
USAGE
}

# Resolve relative paths against the directory containing config.env (script dir)
resolve_path() {
  local p="$1"
  if [[ -z "${p}" ]]; then
    echo ""
  elif [[ "${p}" = /* ]]; then
    echo "${p}"
  else
    echo "${SCRIPT_DIR}/${p}"
  fi
}

# Resolve relative paths against current working directory (CLI inputs)
resolve_cli_path() {
  local p="$1"
  if [[ -z "${p}" ]]; then
    echo ""
  elif [[ "${p}" = /* ]]; then
    echo "${p}"
  else
    echo "$(pwd)/${p}"
  fi
}

run_dir="${RUN_DIR-}"
instance_name=""
run_dir_from_cli=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --run_dir)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      run_dir="$2"
      run_dir_from_cli=true
      shift 2
      ;;
    --run_dir=*)
      run_dir="${1#*=}"
      run_dir_from_cli=true
      shift
      ;;
    --instance_name)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      instance_name="$2"
      shift 2
      ;;
    --instance_name=*)
      instance_name="${1#*=}"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --) shift; break ;;
    -*) break ;;
    *)  break ;;
  esac
done

DEFAULT_RUN_DIR="${SCRIPT_DIR}/run_dir"
if [[ "${run_dir_from_cli}" == true && -n "${run_dir}" ]]; then
  run_dir="$(resolve_cli_path "${run_dir}")"
fi
run_dir="${run_dir:-${DEFAULT_RUN_DIR}}"
run_dir="$(resolve_path "${run_dir}")"

RUN_DIR="${run_dir}"
LOGDIR="${RUN_DIR}/logs"
INSTANCE_NAME_FILE="${LOGDIR}/instance_name.txt"

if [[ -z "${instance_name}" && -f "${INSTANCE_NAME_FILE}" ]]; then
  instance_name="$(head -n 1 "${INSTANCE_NAME_FILE}" | tr -d '\r\n')"
fi

APPTAINER_BIN=""
if [[ -n "${APPTAINER_DIR-}" && "${APPTAINER_DIR}" != /* ]]; then
  APPTAINER_DIR="${SCRIPT_DIR}/${APPTAINER_DIR}"
fi
if [[ -n "${APPTAINER_DIR-}" ]]; then
  candidate_bin="${APPTAINER_DIR%/}/apptainer"
  if [[ -x "${candidate_bin}" ]]; then
    APPTAINER_BIN="${candidate_bin}"
  fi
fi
if [[ -z "${APPTAINER_BIN}" ]]; then
  apptainer_bin="$(command -v apptainer || true)"
  if [[ -z "${apptainer_bin}" ]]; then
    if [[ -n "${APPTAINER_DIR-}" ]]; then
      echo "ERROR: apptainer not found at ${APPTAINER_DIR%/}/apptainer and not found on PATH. Set APPTAINER_DIR in config.env." >&2
    else
      echo "ERROR: apptainer not found on PATH. Set APPTAINER_DIR in config.env." >&2
    fi
    exit 1
  fi
  APPTAINER_BIN="${apptainer_bin}"
fi

list_instances() {
  "${APPTAINER_BIN}" instance list 2>/dev/null | awk 'NR>1 {print $1}'
}

list_madagents_instances() {
  list_instances | grep -E '^madagents($|-)' || true
}

instance_exists() {
  local name="$1"
  list_instances | grep -Fxq "${name}"
}

if [[ -z "${instance_name}" ]]; then
  echo "WARN: no instance name provided and ${INSTANCE_NAME_FILE} not found or empty." >&2
  madagents_instances="$(list_madagents_instances)"
  if [[ -n "${madagents_instances}" ]]; then
    count="$(echo "${madagents_instances}" | wc -l | tr -d ' ')"
    echo "WARN: ${count} madagents instance(s) still running:" >&2
    echo "${madagents_instances}" >&2
    echo "Use --instance_name NAME to stop a specific instance." >&2
    exit 1
  fi
  echo "madrun is already closed."
  exit 0
fi

if instance_exists "${instance_name}"; then
  "${APPTAINER_BIN}" instance stop "${instance_name}"
  echo "madrun is closed now."
  exit 0
fi

echo "madrun is already closed."
madagents_instances="$(list_madagents_instances)"
if [[ -n "${madagents_instances}" ]]; then
  count="$(echo "${madagents_instances}" | wc -l | tr -d ' ')"
  echo "WARN: ${count} madagents instance(s) still running:" >&2
  echo "${madagents_instances}" >&2
  echo "Use --instance_name NAME to stop a specific instance." >&2
fi
