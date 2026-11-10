#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
python -m pip install \
  'fastapi>=0.115,<1' 'SQLAlchemy>=2,<3' 'pydantic>=2.9,<3' \
  'httpx>=0.28,<1' 'google-genai>=1.55,<3' tzdata
python -m unittest discover -s backend/tests -v
