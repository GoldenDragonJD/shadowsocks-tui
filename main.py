#!/usr/bin/env python3
"""Entry point for Shadowsocks TUI Client."""

import sys
from pathlib import Path

# Automatically ensure repository root and venv site-packages are in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

for p in BASE_DIR.glob("venv/lib/python*/site-packages"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shadowsocks_tui.main import main

if __name__ == "__main__":
    main()
