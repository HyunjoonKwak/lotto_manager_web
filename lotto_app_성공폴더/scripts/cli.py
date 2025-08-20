from __future__ import annotations
import os, sys, json
from dotenv import load_dotenv
load_dotenv()

from app.db import (
    init_db, upsert_draw, insert_shops,
    get_draw, get_shops, recent_rounds,
    get_latest_round, stale_before, delete_shops
)
from app.fetchers import (
    fetch_numbers, parse_numbers,
    fetch_shops_html, parse_shops
)

TTL_DAYS = int(os.environ.get("CACHE_TTL_DAYS", "30"))

def usage():
    print("""
사용법:
  python -m scripts.cli init-db
  python -m scripts.cli fetch-round <회차>
  python -m scripts.cli fetch-latest <개수>
  python -m scripts.cli show-round <회차>
  python -m scripts.cli show-latest [개수=10]
  python -m scripts.cli rebuild-shops <회차>   # 당첨점 강제 재수집
""".strip())

def cmd_init_db():
    init_db()
    print("DB 초기화 완료")

def fetch_and_store_round(round_: int, force_shops: bool=False):
    # 번호 수집/저장
    data = fetch_numbers(round_)
    date_str, nums, bonus = parse_numbers(data)
    upsert_draw(round_, date_str, nums, bonus, json.dumps(data, ensure_ascii=False))
    print(f"[번호] {round_}회 = {nums} + ({bonus}) / {date_str}")

    # 당첨점: TTL 기준 캐시 사용, 필요 시 재수집
    need_fetch = force_shops
    if not need_fetch:
        rows = get_shops(round_)
        if not rows:
            need_fetch = True
        else:
            oldest = min(r["fetched_at"] for r in rows)
            if oldest < stale_before(TTL_DAYS):
                need_fetch = True

    if need_fetch:
        html = fetch_shops_html(round_)
        dump = f"/tmp/winshops_{round_}.html"
        try:
            with open(dump, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[debug] HTML 저장: {dump}")
        except Exception as e:
            print(f"[debug] HTML 저장 실패: {e}")

        rows = parse_shops(html, round_)
        # 기존 데이터 제거 후 삽입(헤더 순서 변경으로 과거 잘못 매핑된 행 정리 목적)
        delete_shops(round_)
        insert_shops(round_, rows)
        print(f"[당첨점] {round_}회: {len(rows)}개 저장")
    else:
        print(f"[당첨점] {round_}회: 캐시 사용 (TTL {TTL_DAYS}일)")

def cmd_fetch_round(round_: int):
    fetch_and_store_round(round_, force_shops=False)

def cmd_fetch_latest(count: int):
    got = 0
    base = get_latest_round() or 1
    probe = max(base, 1000)
    # 최신 회차 추정
    while True:
        try:
            data = fetch_numbers(probe)
            if data.get("returnValue") == "success":
                probe += 1
                continue
        except Exception:
            pass
        latest = probe - 1
        break
    print(f"[info] 최신 회차: {latest}")
    start = max(1, latest - count + 1)
    for r in range(start, latest+1):
        cmd_fetch_round(r)

def cmd_show_round(round_: int):
    d = get_draw(round_)
    if not d:
        print(f"{round_}회 DB에 없음 → 수집")
        cmd_fetch_round(round_)
        d = get_draw(round_)
    print(f"{d['round']}회  날짜={d['draw_date']}  번호={[d['n1'],d['n2'],d['n3'],d['n4'],d['n5'],d['n6']]} + ({d['bonus']})")
    shops = get_shops(round_)
    print(f"1등 당첨점 ({len(shops)}곳):")
    for s in shops:
        print(f" - {s['name']} | {s['address'] or '-'} | {s['type'] or '-'}")

def cmd_show_latest(count: int=10):
    rows = recent_rounds(limit=count)
    for d in rows:
        print(f"[{d['round']}] {d['draw_date']} -> {[d['n1'],d['n2'],d['n3'],d['n4'],d['n5'],d['n6']]} +({d['bonus']})")

def cmd_rebuild_shops(round_: int):
    fetch_and_store_round(round_, force_shops=True)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage(); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "init-db":
        cmd_init_db()
    elif cmd == "fetch-round":
        if len(sys.argv) != 3: usage(); sys.exit(1)
        cmd_fetch_round(int(sys.argv[2]))
    elif cmd == "fetch-latest":
        if len(sys.argv) != 3: usage(); sys.exit(1)
        cmd_fetch_latest(int(sys.argv[2]))
    elif cmd == "show-round":
        if len(sys.argv) != 3: usage(); sys.exit(1)
        cmd_show_round(int(sys.argv[2]))
    elif cmd == "show-latest":
        n = int(sys.argv[2]) if len(sys.argv) == 3 else 10
        cmd_show_latest(n)
    elif cmd == "rebuild-shops":
        if len(sys.argv) != 3: usage(); sys.exit(1)
        cmd_rebuild_shops(int(sys.argv[2]))
    else:
        usage(); sys.exit(1)
