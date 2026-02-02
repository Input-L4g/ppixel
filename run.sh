#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(readlink -f -- "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd)"

source "$SCRIPT_DIR/.venv/bin/activate"
exec python3 "$SCRIPT_DIR/run.py" "$@"
