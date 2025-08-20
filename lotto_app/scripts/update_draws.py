#!/usr/bin/env python3
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.services.lotto_fetcher import fetch_latest_known

app = create_app()
with app.app_context():
    res = fetch_latest_known()
    if res:
        print(f"Updated to round {res.round}")
    else:
        print("No new draw.")
