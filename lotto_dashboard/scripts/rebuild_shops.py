#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, re, time
from contextlib import contextmanager
from typing import Tuple, List, Dict, Optional

# 프로젝트 루트 추가
ROOT = "/volume1/code_work/lotto_dashboard"
sys.path.append(ROOT)

# Flask/SQLAlchemy 앱, 모델 로드
from app import create_app
from app.extensions import db

# 모델 클래스명이 대문자여도 실제 테이블은 소문자일 수 있음(ORM가 매핑)
from app.models import Draw, Shop

app = create_app()

# fetch_shops 가져오기 (update_data.py 우선, 없으면 utils.scraper)
fetch_shops = None
try:
    sys.path.append(os.path.join(ROOT, "scripts"))
    import update_data as up
    if hasattr(up, "fetch_shops"):
        fetch_shops = up.fetch_shops
except Exception:
    pass

if fetch_shops is None:
    try:
        from app.utils.scraper import fetch_shops  # 실제 위치에 맞게 조정 필요 가능
    except Exception as e:
        raise RuntimeError("fetch_shops 함수를 찾을 수 없습니다. update_data.py 또는 app/utils/scraper.py 위치를 확인하세요.") from e

BAD_NAME_PATTERNS = (
    r'^\s*\d+\s*~\s*\d+',     # "601~1185" 같은 범위 문자열
    r'전체\s*지역\s*상호',      # "전체 지역 상호"
)

def normalize_rank(raw: Optional[object]) -> Optional[int]:
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw
    s = str(raw)
    m = re.search(r'(\d+)\s*등', s)
    if m:
        return int(m.group(1))
    m = re.search(r'\d+', s)
    return int(m.group(0)) if m else None

def looks_like_garbage_name(name: Optional[str]) -> bool:
    if not name:
        return True
    s = str(name).strip()
    if len(s) > 200:  # 페이지 전체 텍스트가 들어간 의심
        return True
    for pat in BAD_NAME_PATTERNS:
        if re.search(pat, s):
            return True
    return False

@contextmanager
def ctx():
    with app.app_context():
        yield

def backfill_shops_one_round(round_no: int) -> Tuple[int, int]:
    """
    해당 회차를 스크래핑해서 필터/정규화 후 shops 테이블에 저장.
    returns: (raw_count, saved_count)
    """
    rows: List[Dict] = fetch_shops(round_no)
    raw_count = len(rows)
    cleaned: List[Dict] = []

    for r in rows:
        nm = (r.get("name") or "").strip()
        if looks_like_garbage_name(nm):
            continue
        rnk = normalize_rank(r.get("rank"))
        addr = (r.get("address") or "").strip() or None
        method = (r.get("method") or "").strip() or None

        # lon/lng 혼용 대응
        lon = r.get("lon")
        if lon is None:
            lon = r.get("lng")

        cleaned.append(dict(
            round = r.get("round") or round_no,
            rank  = rnk,
            name  = nm,
            address = addr,
            method  = method,
            lat   = r.get("lat") or None,
            lon   = lon or None,
        ))

    # 필요 시 동일 회차 기존 데이터 삭제하고 재삽입하려면 아래 주석 해제
    # db.session.query(Shop).filter_by(round=round_no).delete()

    for c in cleaned:
        db.session.add(Shop(**c))
    db.session.commit()
    return raw_count, len(cleaned)

def latest_round() -> Optional[int]:
    return db.session.query(db.func.max(Draw.round)).scalar()

def main():
    import argparse
    p = argparse.ArgumentParser(description="Shops rebuild with safe filtering & normalization")
    p.add_argument("--round", type=int, help="특정 회차만 수집")
    p.add_argument("--last", type=int, default=10, help="최신 회차부터 N회 수집 (기본 10)")
    args = p.parse_args()

    with ctx():
        if args.round:
            rounds = [args.round]
        else:
            lr = latest_round()
            if not lr:
                print("[ERR] draws 테이블에 데이터가 없습니다. 먼저 추첨 데이터부터 채우세요.")
                return
            start = max(1, lr - args.last + 1)
            rounds = list(range(start, lr + 1))

        total_raw = total_saved = 0
        for r in rounds:
            t0 = time.time()
            try:
                raw, saved = backfill_shops_one_round(r)
                print(f"[shops] round={r} raw={raw} saved={saved} time={time.time()-t0:.2f}s")
                total_raw  += raw
                total_saved+= saved
            except Exception as e:
                db.session.rollback()
                print(f"[ERR] round={r} 실패: {e!r}")
        print(f"[DONE] rounds={rounds[0]}..{rounds[-1]} total_raw={total_raw} total_saved={total_saved}")

if __name__ == "__main__":
    main()
