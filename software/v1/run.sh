#!/usr/bin/env bash
# Touchless Controller v1.0.0 — dev convenience launcher (Linux/macOS).
# The supported target is Windows 10/11 (see run.bat); this script is
# only for running the test suite / headless core during development.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
  .venv/bin/python -m pip install -q -U pip
  .venv/bin/python -m pip install -q -r requirements.txt -r requirements-dev.txt
fi
PYTHONPATH="$PWD/src" exec .venv/bin/python -m touchless "$@"
