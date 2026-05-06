#!/usr/bin/env bash
set -euo pipefail

python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
python -m pytest -q
