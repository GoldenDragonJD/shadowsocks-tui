#!/usr/bin/env bash
# ==============================================================================
# Launcher for Shadowsocks TUI Client
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f "./venv/bin/python" ]]; then
    exec ./venv/bin/python main.py "$@"
else
    exec python3 main.py "$@"
fi
