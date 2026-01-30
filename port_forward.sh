#!/usr/bin/env bash

# SSH destination in user@host (or host) form; required for the port forward to connect.
# Set this manually in the script before running.
SSH_TARGET=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --port)
      ports="$2"   # allow comma-separated list
      shift 2
      ;;
    *)
      echo "Usage: $0 --port PORT[,PORT2,...]"
      exit 1
      ;;
  esac
done

if [ -z "$SSH_TARGET" ]; then
  echo "Error: SSH_TARGET must be set in the script."
  echo "Usage: $0 --port PORT[,PORT2,...]"
  exit 1
fi

if [ -z "$ports" ]; then
  echo "Error: --port is required."
  echo "Usage: $0 --port PORT[,PORT2,...]"
  exit 1
fi

# Build ssh command with one -L per port
IFS=',' read -ra PORT_LIST <<< "$ports"

SSH_ARGS=(-N)
for p in "${PORT_LIST[@]}"; do
  SSH_ARGS+=(-L "${p}:127.0.0.1:${p}")
done
SSH_ARGS+=("$SSH_TARGET")

ssh "${SSH_ARGS[@]}"
