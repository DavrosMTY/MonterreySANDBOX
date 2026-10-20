#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PIP_CACHE_DIR="/workspace/.cache/monterrey-pip"
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.lock.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
if command -v blender >/dev/null 2>&1; then
    blender --version
else
    echo "Blender no disponible: el pipeline geométrico puede ejecutarse; los renders requieren Blender."
fi
