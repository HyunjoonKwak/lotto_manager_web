# app/utils/shops.py
from __future__ import annotations

import os
import sqlite3
from typing import Iterable, List, Dict, Any
from flask import current_app

# -----------------------------------------------------------
# DB 경로 도우미
# -----------------------------------------------------------

def _db_path(app) -> str:
    # Flask instance/ 아래 sqlite 파일
    inst_dir = getattr(app, "instance_path", None) or os.path.join(os.getcwd(), "instance")
    os.makedirs(inst_dir, exist_ok=True)
    return os.path.join(inst_dir, "lotto.db")

# -----------------------------------------------------------
# 파라미터 파싱
# -----------------------------------------------------------

def parse_ranks(s: str | None) -> List[int]:
    """
    "1,2" -> [1,2], 빈값/None이면 [1]
    잘못된 값은 무시.
    """
    if not s:
        return [1]
    out: List[int] = []
    for tok in s.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            v = int(tok)
        except ValueError:
            continue
        if v in (1, 2):
            out.append(v)
    return out or [1]

def _like(s: str) -> str:
    return f"%{s.strip()}%"

# -----------------------------------------------------------
# 조회 유틸
# -----------------------------------------------------------

def fetch_rows(app, round_no: int, ranks: Iterable[int], q: str | None = None) -> List[Dict[str, Any]]:
    """
    shops 테이블에서 행을 조회.
    """
    path = _db_path(app)
    rows: List[Dict[str, Any]] = []
    ranks = list(ranks) or [1]

    where = ["round = ?"]
    params: List[Any] = [round_no]

    if ranks:
        where.append(f"rank IN ({','.join('?' for _ in ranks)})")
        params.extend(ranks)

    if q:
        where.append("(name LIKE ? OR address LIKE ?)")
        params.extend([_like(q), _like(q)])

    sql = f"""
        SELECT round, rank, name, address, method, lat, lon
        FROM shops
        WHERE {' AND '.join(where)}
        ORDER BY rank, COALESCE(address,''), name
    """

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            for r in conn.execute(sql, params).fetchall():
                rows.append(dict(r))
        except sqlite3.OperationalError as e:
            # 테이블이 없는 경우 깔끔히 빈 목록
            if "no such table: shops" in str(e):
                return []
            raise
    return rows

def category_counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """
    기존 템플릿 호환용(분류 합계). 현재 스키마에 category가 없으면 '기타'로 묶음.
    """
    cnt: Dict[str, int] = {}
    for r in rows:
        key = (r.get("category") or "기타").strip() or "기타"
        cnt[key] = cnt.get(key, 0) + 1
    # 보기 좋게 '로또판매점' 우선
    ordered = {}
    for k in sorted(cnt.keys(), key=lambda x: (x != "로또판매점", x)):
        ordered[k] = cnt[k]
    return ordered

# -----------------------------------------------------------
# 자동 강제 크롤링 트리거
# -----------------------------------------------------------

def ensure_shops(app, round_no: int, ranks: Iterable[int], *, force: bool = False) -> int:
    """
    필요한 경우 크롤러를 돌려서 shops 데이터를 보장.
    - force=True: 무조건 크롤링 후 병합
    - force=False: 해당 round/ranks 가 비어있을 때만 크롤링

    return: 새로 적재된(또는 갱신된) row 수의 합계(int)
    """
    ranks = list(ranks) or [1]

    # 1) 미리 DB에 있는지 확인
    total_inserted = 0
    if not force:
        existing = fetch_rows(app, round_no, ranks, q=None)
        if existing:
            return 0  # 이미 있음

    # 2) 크롤러 호출 (scripts.fetch_shops_override.fetch_shops)
    try:
        from scripts.fetch_shops_override import fetch_shops  # type: ignore
    except Exception as e:
        try:
            # 백업 경로 (프로젝트 루트에서 실행 상황 대비)
            from lotto_dashboard.scripts.fetch_shops_override import fetch_shops  # type: ignore
        except Exception:
            current_app.logger.warning("[ensure_shops] cannot import fetch_shops_override: %s", e)
            return 0

    # 크롤러는 내부적으로 instance/lotto.db 에 upsert(또는 insert or ignore) 하도록 설계.
    # 반환값은 '삽입(또는 갱신)된 개수(int)'.
    for r in ranks:
        try:
            inserted = fetch_shops(round_no, r)
        except Exception as e:
            current_app.logger.exception("[ensure_shops] fetch failed: round=%s ranks=%s err=%s", round_no, ranks, e)
            inserted = 0
        total_inserted += (inserted or 0)

    return total_inserted
