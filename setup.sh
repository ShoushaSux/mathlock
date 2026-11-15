#!/usr/bin/env bash
# One-command setup for Linux/macOS (UI development; Windows-only behaviour is a no-op).
# Creates .venv and installs MathLock + dev tools. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "[setup] Python 3.11+ is required (set PYTHON=/path/to/python)." >&2; exit 1; }
"$PY" -c 'import tkinter' 2>/dev/null \
  || { echo "[setup] tkinter missing (e.g. 'sudo dnf install python3-tkinter' or 'sudo apt install python3-tk')." >&2; exit 1; }

[ -x .venv/bin/python ] || { echo "[setup] Creating virtual environment in .venv ..."; "$PY" -m venv .venv; }
echo "[setup] Installing dependencies ..."
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -e ".[dev]" --quiet

echo
echo "[setup] Done! Next steps:"
echo "    source .venv/bin/activate"
echo "    python -m mathlock --now"
