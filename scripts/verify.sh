#!/usr/bin/env bash
set -euo pipefail
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest
mvia drift --config examples/offline.yaml --desired examples/desired.yaml

