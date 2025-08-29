# app/utils/scraper.py
from __future__ import annotations

import os
import json
import time
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import current_app

# ---------------------------------------------------------------------
# 공통 경로/DB 헬퍼
# ---------------------------------------------------------------------

def _db_path(app) -> str:
    inst_dir = getattr(app, "instance_path", None) or os.path.join(os.getcwd(), "instance")
    os.makedirs(inst_dir, exist_ok=True)
    return os.path.join(inst_dir, "lotto.db")

def _connect(app) -> sqlite3.Connection:
    path = _db_path(app)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS numbers (
            round      INTEGER PRIMARY KEY,
            n1         INTEGER NOT NULL,
            n2         INTEGER NOT NULL,
            n3         INTEGER NOT NULL,
            n4         INTEGER NOT NULL,
            n5         INTEGER NOT NULL,
            n6         INTEGER NOT NULL,
            bn         INTEGER NOT NULL,
            draw_date  TEXT
        )
    """)
    # shops 테이블은 다른 유틸에서 생성/관리하지만, 없는 환경에서도 깨지지 않도록만 보장
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shops (
            round   INTEGER NOT NULL,
            rank    INTEGER NOT NULL,
            name    TEXT    NOT NULL,
            address TEXT DEFAULT '',
            method  TEXT,
            lat     REAL,
            lon     REAL,
            source_url TEXT,
            fetched_at INTEGER,
            PRIMARY KEY (round, rank, name, address)
        )
    """)
    return conn

# ---------------------------------------------------------------------
# 동행복권 API
#   https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round}
#   성공 시: {"returnValue":"success", "drwNo":1185, "drwtNo1":.., ..., "bnusNo":.., "drwNoDate":"YYYY-MM-DD"}
#   실패 시: {"returnValue":"fail"}
# ---------------------------------------------------------------------

_API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round}"

def api_get_numbers(round_no: int, *, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    url = _API_URL.format(round=round_no)
    r = requests.get(url, timeout=timeout, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,*/*;q=0.9",
        "Connection": "keep-alive",
    })
    # 일부 환경에서 text/html 로 오기도 해서 강제로 json 파싱 시도
    try:
        data = r.json()
    except json.JSONDecodeError:
        # 응답이 비정상일 수 있으므로 방어
        try:
            data = json.loads(r.text)
        except Exception:
            return None
    if not isinstance(data, dict):
        return None
    if data.get("returnValue") != "success":
        return None
    return data

def parse_numbers(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        return {
            "round": int(payload["drwNo"]),
            "n1": int(payload["drwtNo1"]),
            "n2": int(payload["drwtNo2"]),
            "n3": int(payload["drwtNo3"]),
            "n4": int(payload["drwtNo4"]),
            "n5": int(payload["drwtNo5"]),
            "n6": int(payload["drwtNo6"]),
            "bn": int(payload["bnusNo"]),
            "draw_date": str(payload.get("drwNoDate") or ""),
        }
    except Exception:
        return None

# ---------------------------------------------------------------------
# DB upsert & range fetch
# ---------------------------------------------------------------------

def upsert_numbers(app, row: Dict[str, Any]) -> int:
    with _connect(app) as conn:
        cur = conn.execute("""
            INSERT INTO numbers (round, n1,n2,n3,n4,n5,n6,bn,draw_date)
            VALUES (:round, :n1,:n2,:n3,:n4,:n5,:n6,:bn,:draw_date)
            ON CONFLICT(round) DO UPDATE SET
              n1=excluded.n1, n2=excluded.n2, n3=excluded.n3,
              n4=excluded.n4, n5=excluded.n5, n6=excluded.n6,
              bn=excluded.bn, draw_date=excluded.draw_date
        """, row)
        conn.commit()
        # sqlite3의 rowcount는 upsert 결과에 따라 1 또는 0일 수 있음
        return 1

def fetch_and_store_round(app, round_no: int, *, sleep_sec: float = 0.2) -> bool:
    """단일 회차를 API에서 받아 DB에 upsert. 성공시 True"""
    data = api_get_numbers(round_no)
    if not data:
        return False
    row = parse_numbers(data)
    if not row:
        return False
    upsert_numbers(app, row)
    current_app.logger.info("[numbers] upsert round=%s %s", row["round"], row["draw_date"])
    time.sleep(sleep_sec)
    return True

def fetch_numbers_range(app, start_round: int, end_round: int, *, stop_on_fail: bool = False) -> int:
    """start_round..end_round 범위를 순회하며 적재. 반환=성공(저장) 건수"""
    if start_round > end_round:
        start_round, end_round = end_round, start_round
    saved = 0
    for r in range(start_round, end_round + 1):
        ok = fetch_and_store_round(app, r)
        if ok:
            saved += 1
        elif stop_on_fail:
            break
    return saved

# ---------------------------------------------------------------------
# 최신 회차 탐색 로직
#   - DB에 있는 최대 회차 다음부터 1씩 올려가며 success 뜨는 최대 회차까지 수집
#   - 실패가 연속으로 나타나면 중단
# ---------------------------------------------------------------------

def get_db_max_round(app) -> int:
    path = _db_path(app)
    if not os.path.exists(path):
        return 0
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT MAX(round) FROM numbers").fetchone()
        return int(row[0]) if row and row[0] is not None else 0

def fetch_latest_until_fail(app, *, max_probe: int = 10) -> Tuple[int, int]:
    """
    DB 내 최대회차+1부터 API success가 끊길 때까지 최대 max_probe 번 시도.
    반환: (시작회차, 저장건수)
    """
    start = get_db_max_round(app) + 1
    if start <= 0:
        start = 1
    saved = 0
    fail_streak = 0
    r = start
    while fail_streak < 2 and (saved + fail_streak) < max_probe:
        ok = fetch_and_store_round(app, r)
        if ok:
            saved += 1
            fail_streak = 0
        else:
            fail_streak += 1
        r += 1
    return start, saved

# ---------------------------------------------------------------------
# 대시보드에서 호출하는 “최근 N회” 갱신 도우미
#   - DB의 최대 회차를 기준으로 거꾸로 recent개 만큼 채워넣음
#   - 비어 있으면 최신까지 탐색 후 recent 개수 보장
# ---------------------------------------------------------------------

def update_recent_data(app, *, recent: int = 5) -> Dict[str, Any]:
    """
    최근 N회 데이터를 보장. (없으면 API로 채움)
    반환: {"filled": 채운개수, "from": 시작회차, "to": 끝회차}
    """
    if recent <= 0:
        recent = 5

    max_in_db = get_db_max_round(app)
    filled = 0
    start_round = max(1, max_in_db - recent + 1)
    end_round = max_in_db

    if max_in_db == 0:
        # 비어 있으면 최신부터 먼저 찾아 넣음
        _, got = fetch_latest_until_fail(app, max_probe=max(recent + 2, 6))
        max_in_db = get_db_max_round(app)
        start_round = max(1, max_in_db - recent + 1)
        end_round = max_in_db
        filled += got

    # 최근 N회 구간 보장
    if end_round >= start_round:
        got2 = fetch_numbers_range(app, start_round, end_round)
        filled += got2

    current_app.logger.info("[numbers] update_recent_data recent=%s -> filled=%s (%s..%s)",
                            recent, filled, start_round, end_round)
    return {"filled": filled, "from": start_round, "to": end_round}
