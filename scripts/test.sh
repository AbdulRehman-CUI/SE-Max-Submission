#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
python -m pip install -r backend/requirements.txt
python -m unittest discover -s backend/tests -v
