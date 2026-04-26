#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

make -C "${REPO_ROOT}/Game1/antgame_cpp_sdk" -j4 build/sdk_lure_inspector
exec python3 "${SCRIPT_DIR}/server.py" "$@"
