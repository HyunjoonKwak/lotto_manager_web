#!/bin/bash
set -e
ROOT="/volume1/code_work/lotto_dashboard"
source "$ROOT/.venv/bin/activate"
cd "$ROOT"
python scripts/update_data.py --update
deactivate
