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

# ---------- usage ----------
usage() {
  cat <<'USAGE'
Usage: madrun.sh [options] [-- <extra args passed to madrun_main.py>]

Options:
  -o, --output_dir DIR          Output directory
      --run_dir DIR             Run directory
  -p, --project_dir DIR         Project directory (defaults to script location)
      --apptainer_dir DIR       Directory containing apptainer binary
      --apptainer_cachedir DIR  Apptainer cache directory
      --apptainer_configdir DIR Apptainer config directory
      --npm_config_cache DIR    NPM cache directory
      --frontend_port PORT      Frontend port (default: 5173)
      --backend_port PORT       Backend port (default: 8000)
  -h, --help                    Show this help and exit

Notes:
  - CLI path arguments are resolved relative to the current working directory.
  - config.env path values are resolved relative to this script's directory.
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

# ---------- args ----------
output_dir="${OUTPUT_DIR-}"
run_dir="${RUN_DIR-}"
apptainer_dir="${APPTAINER_DIR-}"
apptainer_cachedir="${APPTAINER_CACHEDIR-}"
apptainer_configdir="${APPTAINER_CONFIGDIR-}"
npm_config_cache="${NPM_CONFIG_CACHE-}"
frontend_port="${FRONTEND_PORT-}"
backend_port="${BACKEND_PORT-}"
project_dir=""
output_dir_from_cli=false
run_dir_from_cli=false
apptainer_dir_from_cli=false
apptainer_cachedir_from_cli=false
apptainer_configdir_from_cli=false
npm_config_cache_from_cli=false
project_dir_from_cli=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o|--output_dir)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      output_dir="$2"
      output_dir_from_cli=true
      shift 2
      ;;
    --output_dir=*)
      output_dir="${1#*=}"
      output_dir_from_cli=true
      shift
      ;;
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
    -p|--project_dir)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      project_dir="$2"
      project_dir_from_cli=true
      shift 2
      ;;
    --project_dir=*)
      project_dir="${1#*=}"
      project_dir_from_cli=true
      shift
      ;;
    --apptainer_dir)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      apptainer_dir="$2"
      apptainer_dir_from_cli=true
      shift 2
      ;;
    --apptainer_dir=*)
      apptainer_dir="${1#*=}"
      apptainer_dir_from_cli=true
      shift
      ;;
    --apptainer_cachedir)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      apptainer_cachedir="$2"
      apptainer_cachedir_from_cli=true
      shift 2
      ;;
    --apptainer_cachedir=*)
      apptainer_cachedir="${1#*=}"
      apptainer_cachedir_from_cli=true
      shift
      ;;
    --apptainer_configdir)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      apptainer_configdir="$2"
      apptainer_configdir_from_cli=true
      shift 2
      ;;
    --apptainer_configdir=*)
      apptainer_configdir="${1#*=}"
      apptainer_configdir_from_cli=true
      shift
      ;;
    --npm_config_cache)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      npm_config_cache="$2"
      npm_config_cache_from_cli=true
      shift 2
      ;;
    --npm_config_cache=*)
      npm_config_cache="${1#*=}"
      npm_config_cache_from_cli=true
      shift
      ;;
    --frontend_port)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      frontend_port="$2"
      shift 2
      ;;
    --frontend_port=*)
      frontend_port="${1#*=}"
      shift
      ;;
    --backend_port)
      [[ $# -ge 2 ]] || { echo "Error: $1 requires a value" >&2; exit 2; }
      backend_port="$2"
      shift 2
      ;;
    --backend_port=*)
      backend_port="${1#*=}"
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

# ---------- paths / vars ----------
if [[ -z "${project_dir}" ]]; then
  project_dir="${SCRIPT_DIR}"
elif [[ "${project_dir_from_cli}" == true ]]; then
  project_dir="$(resolve_cli_path "${project_dir}")"
fi
project_dir="$(resolve_path "${project_dir}")"
PROJECT_DIR="${project_dir}"

DEFAULT_OUTPUT_DIR="${PROJECT_DIR}/output"
DEFAULT_RUN_DIR="${PROJECT_DIR}/run_dir"
DEFAULT_APPTAINER_CACHEDIR="${PROJECT_DIR}/.apptainer/cache"
DEFAULT_APPTAINER_CONFIGDIR="${PROJECT_DIR}/.apptainer"
DEFAULT_NPM_CONFIG_CACHE="${PROJECT_DIR}/.npm"
DEFAULT_FRONTEND_PORT=5173
DEFAULT_BACKEND_PORT=8000

if [[ "${output_dir_from_cli}" == true && -n "${output_dir}" ]]; then
  output_dir="$(resolve_cli_path "${output_dir}")"
fi
if [[ "${run_dir_from_cli}" == true && -n "${run_dir}" ]]; then
  run_dir="$(resolve_cli_path "${run_dir}")"
fi
if [[ "${apptainer_dir_from_cli}" == true && -n "${apptainer_dir}" ]]; then
  apptainer_dir="$(resolve_cli_path "${apptainer_dir}")"
fi
if [[ "${apptainer_cachedir_from_cli}" == true && -n "${apptainer_cachedir}" ]]; then
  apptainer_cachedir="$(resolve_cli_path "${apptainer_cachedir}")"
fi
if [[ "${apptainer_configdir_from_cli}" == true && -n "${apptainer_configdir}" ]]; then
  apptainer_configdir="$(resolve_cli_path "${apptainer_configdir}")"
fi
if [[ "${npm_config_cache_from_cli}" == true && -n "${npm_config_cache}" ]]; then
  npm_config_cache="$(resolve_cli_path "${npm_config_cache}")"
fi

output_dir="${output_dir:-${DEFAULT_OUTPUT_DIR}}"
run_dir="${run_dir:-${DEFAULT_RUN_DIR}}"
apptainer_cachedir="${apptainer_cachedir:-${DEFAULT_APPTAINER_CACHEDIR}}"
apptainer_configdir="${apptainer_configdir:-${DEFAULT_APPTAINER_CONFIGDIR}}"
npm_config_cache="${npm_config_cache:-${DEFAULT_NPM_CONFIG_CACHE}}"
frontend_port="${frontend_port:-${DEFAULT_FRONTEND_PORT}}"
backend_port="${backend_port:-${DEFAULT_BACKEND_PORT}}"

output_dir="$(resolve_path "${output_dir}")"
run_dir="$(resolve_path "${run_dir}")"
apptainer_cachedir="$(resolve_path "${apptainer_cachedir}")"
apptainer_configdir="$(resolve_path "${apptainer_configdir}")"
npm_config_cache="$(resolve_path "${npm_config_cache}")"

if [[ -z "${output_dir}" ]]; then
  echo "Error: output_dir is empty" >&2
  exit 2
fi
if [[ -z "${run_dir}" ]]; then
  echo "Error: run_dir is empty" >&2
  exit 2
fi
if ! [[ "${frontend_port}" =~ ^[0-9]+$ ]]; then
  echo "Error: frontend_port must be an integer" >&2
  exit 2
fi
if ! [[ "${backend_port}" =~ ^[0-9]+$ ]]; then
  echo "Error: backend_port must be an integer" >&2
  exit 2
fi
if (( frontend_port < 1 || frontend_port > 65535 )); then
  echo "Error: frontend_port must be in [1, 65535]" >&2
  exit 2
fi
if (( backend_port < 1 || backend_port > 65535 )); then
  echo "Error: backend_port must be in [1, 65535]" >&2
  exit 2
fi

RUN_DIR="${run_dir}"
OUTPUT_DIR="${output_dir}"
if [[ -n "${apptainer_dir}" ]]; then
  apptainer_dir="$(resolve_path "${apptainer_dir}")"
  APPTAINER_DIR="${apptainer_dir}"
else
  apptainer_bin="$(command -v apptainer || true)"
  if [[ -z "${apptainer_bin}" ]]; then
    echo "ERROR: apptainer not found on PATH. Set --apptainer_dir or APPTAINER_DIR in config.env." >&2
    exit 1
  fi
  APPTAINER_DIR="$(dirname "${apptainer_bin}")"
fi
APPTAINER_CACHEDIR="${apptainer_cachedir}"
APPTAINER_CONFIGDIR="${apptainer_configdir}"
NPM_CONFIG_CACHE="${npm_config_cache}"

mkdir -p -- "${OUTPUT_DIR}"
mkdir -p -- "${RUN_DIR}"
mkdir -p -- "${APPTAINER_CACHEDIR}" "${APPTAINER_CONFIGDIR}" "${NPM_CONFIG_CACHE}"

export APPTAINER_CACHEDIR
export APPTAINER_CONFIGDIR
export NPM_CONFIG_CACHE
export APPTAINERENV_NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE}"

# ---------- lock (prevent simultaneous runs in same clone) ----------
LOCK_FILE="${RUN_DIR}/.madrun.lock"
exec {LOCK_FD}>"${LOCK_FILE}" || { echo "ERROR: cannot open lock file ${LOCK_FILE}" >&2; exit 1; }
if ! flock -n "${LOCK_FD}"; then
  echo "ERROR: madrun is already running for this clone (lock: ${LOCK_FILE})" >&2
  exit 1
fi
printf '%s\n' "$$" 1>&"${LOCK_FD}"

# ---------- port availability ----------
port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk 'NR>1 {print $4}' | awk -F: '{print $NF}' | grep -Fxq "${port}"
    return $?
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - "${port}" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
try:
    s.bind(("0.0.0.0", port))
except OSError:
    sys.exit(0)  # in use
else:
    sys.exit(1)  # free
finally:
    s.close()
PY
    return $?
  fi
  if command -v python >/dev/null 2>&1; then
    python - "${port}" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
try:
    s.bind(("0.0.0.0", port))
except OSError:
    sys.exit(0)  # in use
else:
    sys.exit(1)  # free
finally:
    s.close()
PY
    return $?
  fi
  echo "ERROR: cannot check port availability (need ss, lsof, or python)" >&2
  return 2
}

if port_in_use "${frontend_port}"; then
  echo "ERROR: frontend_port ${frontend_port} is already in use" >&2
  exit 1
fi
if port_in_use "${backend_port}"; then
  echo "ERROR: backend_port ${backend_port} is already in use" >&2
  exit 1
fi

LOGDIR="${RUN_DIR}/logs"
mkdir -p "${LOGDIR}"

SRC_DIR="${PROJECT_DIR}/src"
UI_DIR="${SRC_DIR}/madagents/frontend/ui"
PDF_FILES_DIR="${RUN_DIR}/pdf_files"
mkdir -p -- "${PDF_FILES_DIR}"

APPTAINER_BIN="${APPTAINER_DIR%/}/apptainer"
if [[ ! -x "${APPTAINER_BIN}" ]]; then
  echo "ERROR: apptainer not found at ${APPTAINER_BIN}. Set --apptainer_dir or APPTAINER_DIR in config.env." >&2
  exit 1
fi

IMAGE="${PROJECT_DIR}/image/madagents.sif"
OVERLAY="${PROJECT_DIR}/image/mad_overlay.img"

MADRUN_LOG="${LOGDIR}/madrun.log"
APPTAINER_LOG="${LOGDIR}/apptainer.log"
LINKS_LOG="${LOGDIR}/madagents_links.txt"
INSTANCE_NAME_FILE="${LOGDIR}/instance_name.txt"
SOCK_PATH="/runs/user_bridge/attach.sock"

DRIVER_PID=""
SESSION_STARTED=false
INSTANCE_NAME=""

list_instances() {
  "${APPTAINER_BIN}" instance list 2>/dev/null | awk 'NR>1 {print $1}'
}

instance_exists() {
  local name="$1"
  list_instances | grep -Fxq "${name}"
}

# ---------- cleanup ----------
cleanup() {
  status=$?

  printf '\nClosing MadAgents ...\n'

  # If we started the driver, stop its whole process group
  if [[ -n "${DRIVER_PID-}" ]]; then
    kill -INT -"${DRIVER_PID}" 2>/dev/null || true
    wait "${DRIVER_PID}" 2>/dev/null || true
  fi

  # Stop the apptainer instance if we started one
  if [[ "${SESSION_STARTED}" == "true" && -n "${INSTANCE_NAME}" ]]; then
    "${APPTAINER_BIN}" instance stop "${INSTANCE_NAME}" 2>/dev/null || true
  fi

  exit "$status"
}

trap cleanup EXIT INT TERM HUP

# ---------- pre-run cleanup ----------
rm -rf -- "${RUN_DIR}/user_bridge" || true

# ---------- startup message ----------
echo "Starting MadAgents ..."

# ---------- start instance ----------
# TODO: Use
# --overlay "${OVERLAY}" \
# --overlay "${OVERLAY}":/opt \
INSTANCE_BASE="madagents"
for i in $(seq 0 999); do
  if (( i == 0 )); then
    candidate="${INSTANCE_BASE}"
  else
    candidate="${INSTANCE_BASE}-${i}"
  fi

  if "${APPTAINER_BIN}" instance start \
    --fakeroot \
    -B "${SRC_DIR}:/AgentFitter/src:ro" \
    -B "${UI_DIR}:/AgentFitter/src/madagents/frontend/ui" \
    -B "${PDF_FILES_DIR}:/pdf_files:ro" \
    -B "${output_dir}:/output" \
    -B "${RUN_DIR}:/runs" \
    --overlay "${OVERLAY}" \
    "${IMAGE}" \
    "${candidate}" \
    >"${APPTAINER_LOG}" 2>&1; then
    SESSION_STARTED=true
    INSTANCE_NAME="${candidate}"
    printf '%s\n' "${INSTANCE_NAME}" > "${INSTANCE_NAME_FILE}"
    break
  fi

  if instance_exists "${candidate}"; then
    continue
  fi

  echo "ERROR: failed to start apptainer instance ${candidate}. See ${APPTAINER_LOG}" >&2
  exit 1
done

if [[ -z "${INSTANCE_NAME}" ]]; then
  echo "ERROR: could not find a free apptainer instance name based on ${INSTANCE_BASE}" >&2
  exit 1
fi

# ---------- start driver ----------
setsid "${APPTAINER_BIN}" exec --pwd /output instance://"${INSTANCE_NAME}" \
  /bin/env PYTHONPATH="/AgentFitter/src:${PYTHONPATH:-}" \
  /AgentFitter/envs/Agent/bin/python -m madagents.madrun_main \
  --frontend_port "${frontend_port}" \
  --backend_port "${backend_port}" \
  "$@" \
  >"${MADRUN_LOG}" 2>&1 &
DRIVER_PID=$!

# ---------- wait for socket ----------
session_ready=false
for _ in {1..600}; do
  if "${APPTAINER_BIN}" exec instance://"${INSTANCE_NAME}" test -S "${SOCK_PATH}"; then
    session_ready=true
    break
  fi
  sleep 0.1
done

if ! $session_ready; then
  echo "ERROR: timed out waiting for bridge socket ${SOCK_PATH}" >&2
  exit 1
fi

# ---------- print interface links ----------
links_ready=false
for _ in {1..300}; do
  if [[ -s "${LINKS_LOG}" ]]; then
    links_ready=true
    break
  fi
  sleep 0.1
done

if $links_ready; then
  cat "${LINKS_LOG}"
else
  echo "WARN: interface links not available yet at ${LINKS_LOG}" >&2
fi

# ---------- start local madgraph cli ----------
"${APPTAINER_BIN}" exec --pwd /output instance://"${INSTANCE_NAME}" \
  python /AgentFitter/src/madagents/cli_bridge/attach_client.py \
    --workdir /runs/user_bridge

# When attach_client exits, script exits; cleanup trap will run.
