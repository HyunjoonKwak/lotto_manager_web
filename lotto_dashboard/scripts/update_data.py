import os, sys, time
# add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import argparse
from app import create_app
from app.extensions import db
from app.models import Draw, Recommendation, RecMatch, Shop
from app.utils.scraper import iter_fetch_draws, fetch_shops, fetch_draw

BATCH_SIZE = 200          # 커밋 배치 크기
COMMIT_RETRIES = 3        # 커밋 재시도 횟수
RETRY_BASE_SLEEP = 1.5    # 백오프 기본 초

def commit_with_retry():
    for i in range(COMMIT_RETRIES):
        try:
            db.session.commit()
            return
        except Exception:
            db.session.rollback()
            if i == COMMIT_RETRIES - 1:
                raise
            time.sleep(RETRY_BASE_SLEEP * (2 ** i))

def ensure_draw_row(d):
    """dict d -> Draw insert (중복이면 skip)"""
    with db.session.no_autoflush:
        existed = Draw.query.filter_by(round=d["round"]).first()
    if existed:
        return False
    obj = Draw(
        round=d["round"],
        draw_date=d["draw_date"],
        n1=d["numbers"][0], n2=d["numbers"][1], n3=d["numbers"][2],
        n4=d["numbers"][3], n5=d["numbers"][4], n6=d["numbers"][5],
        bonus=d["bonus"]
    )
    db.session.add(obj)
    return True

def smart_fill_all():
    """DB가 비면 전체 수집."""
    added = 0
    for i, d in enumerate(iter_fetch_draws(1), start=1):
        if ensure_draw_row(d):
            added += 1
        if i % BATCH_SIZE == 0:
            commit_with_retry()
    commit_with_retry()
    return added

def smart_fill_missing():
    """중간 비어있는 회차만 채우기 + 최신 회차 채우기."""
    added = 0
    # 현재 보유 회차 집합
    rounds = [r for (r,) in db.session.query(Draw.round).order_by(Draw.round).all()]
    if not rounds:
        return smart_fill_all()

    min_r, max_r = rounds[0], rounds[-1]
    have = set(rounds)

    # 1) 중간 빈 회차 채우기
    missing = [r for r in range(min_r, max_r + 1) if r not in have]
    if missing:
        for i, r in enumerate(missing, start=1):
            d = fetch_draw(r)
            if d and ensure_draw_row(d):
                added += 1
            if i % BATCH_SIZE == 0:
                commit_with_retry()
        commit_with_retry()

    # 2) 최신 회차 계속 늘려가기
    #    max_r+1부터 성공이 끊길 때까지 수집
    tail_added = 0
    for i, d in enumerate(iter_fetch_draws(max_r + 1), start=1):
        if ensure_draw_row(d):
            added += 1
            tail_added += 1
        if i % BATCH_SIZE == 0:
            commit_with_retry()
    commit_with_retry()

    return added

def analyze_matches(new_round):
    draw = Draw.query.filter_by(round=new_round).first()
    if not draw:
        return 0
    draw_set = set(draw.numbers())
    cnt = 0
    recs = Recommendation.query.all()
    for r in recs:
        nums = set(map(int, r.nums.split(",")))
        matched = sorted(draw_set.intersection(nums))
        m = RecMatch(draw_round=new_round, recommendation_id=r.id,
                     matched_count=len(matched), matched_nums=",".join(map(str, matched)))
        db.session.add(m)
        cnt += 1
    commit_with_retry()
    return cnt

def backfill_shops(round_no):
    with db.session.no_autoflush:
        if Shop.query.filter_by(round=round_no).first():
            return 0
    rows = fetch_shops(round_no)
    for r in rows:
        s = Shop(round=r["round"], rank=r.get("rank"),
                 name=r["name"], address=r.get("address"), method=r.get("method"))
        db.session.add(s)
    commit_with_retry()
    return len(rows)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fetch-all", action="store_true", help="DB가 비면 1회차부터 전체 수집")
    p.add_argument("--from-last", type=int, default=0, help="최근 N회차 범위만 스캔하여 채움")
    p.add_argument("--update", action="store_true", help="최신 회차만 업데이트")
    p.add_argument("--shops", type=int, help="특정 회차 1등 당첨점만 수집")
    p.add_argument("--smart", action="store_true", help="DB 상태를 보고: 비면 전체 / 비어있으면 채움 / 최신 미수집이면 최신만")
    args = p.parse_args()

    app = create_app()
    with app.app_context():
        if args.shops is not None:
            count = backfill_shops(args.shops)
            print(f"[OK] 회차 {args.shops} 당첨점 {count}건 저장")
            return

        # SMART 모드: 기본값 (아무 옵션도 없으면 smart로 동작)
        if args.smart or (not args.fetch_all and args.from_last == 0 and not args.update):
            total = Draw.query.count()
            if total == 0:
                print("[SMART] DB 비어있음 → 전체 수집 시작")
                added = smart_fill_all()
                print(f"[SMART] 전체 수집 완료: 추가 {added}건")
            else:
                print("[SMART] DB 존재 → 중간 빈 회차 채우기 + 최신 회차 갱신")
                added = smart_fill_missing()
                if added:
                    # 최신 회차에 대해 연관성 분석 (마지막 회차 기준)
                    new_round = db.session.query(db.func.max(Draw.round)).scalar()
                    m = analyze_matches(new_round)
                    print(f"[SMART] 수집 {added}건, 연관성 분석 {m}건 저장")
                else:
                    print("[SMART] 추가 없음")
            return

        # 기존 옵션 처리
        if args.fetch_all:
            added = smart_fill_all()
            print(f"[OK] 전체 수집: 추가 {added}건")

        elif args.from_last > 0:
            latest = Draw.query.order_by(Draw.round.desc()).first()
            start = (latest.round - args.from_last + 1) if latest else 1
            added = 0
            for i, d in enumerate(iter_fetch_draws(start), start=1):
                if ensure_draw_row(d):
                    added += 1
                if i % BATCH_SIZE == 0:
                    commit_with_retry()
            commit_with_retry()
            print(f"[OK] 최근 {args.from_last} 범위에서 {added}건 추가")

        elif args.update:
            last = db.session.query(db.func.max(Draw.round)).scalar() or 0
            added = 0
            for i, d in enumerate(iter_fetch_draws(last + 1), start=1):
                if ensure_draw_row(d):
                    added += 1
                if i % BATCH_SIZE == 0:
                    commit_with_retry()
            commit_with_retry()
            if added:
                new_round = db.session.query(db.func.max(Draw.round)).scalar()
                m = analyze_matches(new_round)
                print(f"[OK] 업데이트 {added}건, 연관성 분석 {m}건 저장")
            else:
                print("[OK] 신규 없음")

