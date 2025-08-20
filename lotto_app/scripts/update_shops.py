#!/usr/bin/env python3
import os, sys
# 프로젝트 루트(…/lotto_app)를 파이썬 경로에 추가
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.services.shops_crawler import update_shops_round

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: update_shops.py <round>")
        sys.exit(1)
    round_no = int(sys.argv[1])
    app = create_app()
    with app.app_context():
        res = update_shops_round(round_no)
        print(res)
