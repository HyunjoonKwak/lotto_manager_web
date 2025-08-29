#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
동행복권 '당첨 판매점(배출점)' 크롤러
- 시그니처: fetch_shops(round_no:int, rank:int) -> int
- 역할: 지정 회차/등수(1,2) 판매점 목록을 가져와 instance/lotto.db 의 shops 테이블에 저장
- 반환: insert(or ignore)된 추정 행 수

특징:
- DB 초기화 없이 동작하도록, 연결 시 누락 컬럼(source_url, fetched_at)을 자동 추가
- 1등 테이블은 '구분(자동/수동/반자동)'이 있고, 2등 테이블은 없는 경우가 많음을 반영
- 헤더 기반 + 휴리스틱 병용 파싱
"""

from __future__ import annotations
import os, re, time, sqlite3
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

# -------- 설정 --------

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://dhlottery.co.kr/store.do?method=topStore&pageGubun=L645",
    "Connection": "keep-alive",
}
DUMP_DIR = os.path.join("logs", "shops")
os.makedirs(DUMP_DIR, exist_ok=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTANCE = os.path.join(ROOT, "instance")
os.makedirs(INSTANCE, exist_ok=True)
DB_PATH = os.path.join(INSTANCE, "lotto.db")

# -------- 유틸 --------

def _dump(html: str, round_no: int, rank: int, page: int, tag: str):
    fn = os.path.join(DUMP_DIR, f"{tag}_{round_no}_{rank}_p{page}_{int(time.time())}.debug.html")
    try:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[dump] saved {fn}")
    except Exception as e:
        print(f"[dump:err] {e}")

def _decode(resp: requests.Response) -> str:
    # EUC-KR, UTF-8 혼용 보호
    try:
        return resp.content.decode("euc-kr", errors="ignore")
    except Exception:
        resp.encoding = resp.encoding or "utf-8"
        return resp.text

def _clean(s: Optional[str]) -> str:
    return (s or "").strip()

# -------- DB 연결 + 자동 마이그레이션 --------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)

    # 기본 테이블(가능한한 보수적으로 정의) — 기존 설치본과 충돌 없게
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shops (
            round     INTEGER NOT NULL,
            rank      INTEGER NOT NULL,
            name      TEXT    NOT NULL,
            address   TEXT    NOT NULL DEFAULT '',
            method    TEXT,
            lat       REAL,
            lon       REAL
        )
    """)

    # 누락 컬럼 자동 추가 (source_url, fetched_at)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(shops)").fetchall()}  # row[1] = name
    if "source_url" not in cols:
        try:
            conn.execute("ALTER TABLE shops ADD COLUMN source_url TEXT")
        except sqlite3.OperationalError:
            pass
    if "fetched_at" not in cols:
        try:
            conn.execute("ALTER TABLE shops ADD COLUMN fetched_at INTEGER")
        except sqlite3.OperationalError:
            pass

    # 중복 방지(가능하면 UNIQUE 추가) — 이미 인덱스/제약이 있으면 생략
    try:
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_shops_round_rank_name_addr
            ON shops(round, rank, name, address)
        """)
    except sqlite3.OperationalError:
        pass

    return conn

def _insert_many(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    with _connect() as conn:
        cur = conn.executemany(
            """
            INSERT OR IGNORE INTO shops
              (round, rank, name, address, method, lat, lon, source_url, fetched_at)
            VALUES
              (:round, :rank, :name, :address, :method, :lat, :lon, :source_url, :fetched_at)
            """,
            rows,
        )
        conn.commit()
        return cur.rowcount or 0

# -------- 테이블 탐지/파싱 --------

def _tables_for_rank(soup: BeautifulSoup, rank: int) -> List[BeautifulSoup]:
    """
    rank 구분은 '1등 배출점' / '2등 배출점' 같은 제목 섹션으로 판단:
      - 제목 근처의 첫 테이블 우선
      - 보조로 헤더 키워드 포함 테이블
    """
    found: List[BeautifulSoup] = []

    # 제목 근처
    heads = soup.find_all(["h2", "h3", "strong", "p", "span", "div"])
    for h in heads:
        tx = h.get_text(" ", strip=True)
        if not tx:
            continue
        if (f"{rank}등" in tx) and ("배출점" in tx or "당첨점" in tx or "판매점" in tx):
            t = h.find_next("table")
            if t:
                found.append(t)

    # 키워드 테이블(보조)
    for t in soup.find_all("table"):
        headtxt = t.get_text(" ", strip=True)
        if any(k in headtxt for k in ("상호", "상호명", "판매점", "배출점")) and \
           any(k in headtxt for k in ("주소", "소재지")):
            if t not in found:
                found.append(t)

    return found

def _guess_columns_by_header(table: BeautifulSoup) -> Dict[str, Optional[int]]:
    """
    가능한 헤더 텍스트를 기반으로 name/address/method 인덱스를 추정.
    - 1등 테이블은 '구분(자동/수동/반자동)' 컬럼이 있고
    - 2등 테이블은 '구분'이 없을 수 있음
    """
    idx = {"name": None, "address": None, "method": None}
    thead = table.find("thead")
    ths = (thead.find_all("th") if thead else []) or table.find_all("th")
    for i, th in enumerate(ths or []):
        tx = th.get_text(" ", strip=True)
        if re.search(r"(상호명|판매점명|상호|배출점)", tx):
            idx["name"] = i
        if re.search(r"(소재지|주소)", tx):
            idx["address"] = i
        if re.search(r"(구분|방식)", tx):
            idx["method"] = i
    return idx

def _parse_table(table: BeautifulSoup, round_no: int, rank: int, source_url: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    idx = _guess_columns_by_header(table)
    tbody = table.find("tbody") or table

    for tr in tbody.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) < 2:
            continue

        # 셀 텍스트 모두 전처리
        cells = [_clean(td.get_text(" ", strip=True)) for td in tds]

        def _get(i: Optional[int], fallback: Optional[int]) -> str:
            if i is not None and 0 <= i < len(cells):
                return cells[i]
            if fallback is not None and 0 <= fallback < len(cells):
                return cells[fallback]
            return ""

        # 헤더 매핑 1차
        name = _get(idx["name"], 1 if len(cells) >= 2 else 0)
        address = _get(idx["address"], None)

        # 2차 휴리스틱 보강
        if not name:
            # 링크 텍스트가 상호명인 경우
            a = tr.find("a")
            if a and _clean(a.get_text()):
                name = _clean(a.get_text())

        if not address:
            # 주소 특징어가 들어간 가장 긴 셀
            cand = [c for c in cells if re.search(r"(시|군|구|동|로|길|도|읍|면)", c)]
            if cand:
                address = max(cand, key=len)

        # 구분(자동/수동/반자동) – 1등 테이블엔 존재, 2등엔 보통 없음
        method = None
        if idx["method"] is not None:
            method = _get(idx["method"], None) or None
        if not method:
            for c in cells:
                if re.fullmatch(r"(자동|수동|반자동)", c):
                    method = c
                    break

        # 유효성 검사
        if not name:
            continue

        rows.append({
            "round": round_no,
            "rank": rank,
            "name": name,
            "address": address or "",
            "method": method,
            "lat": None,
            "lon": None,
            "source_url": source_url,
            "fetched_at": int(time.time()),
        })

    # (이름+주소) 기준 중복 제거
    uniq: Dict[tuple, Dict[str, Any]] = {}
    for r in rows:
        key = (r["name"], r["address"])
        uniq[key] = r
    return list(uniq.values())

# -------- 실제 크롤링 --------

def fetch_shops(round_no: int, rank: int) -> int:
    """
    지정 회차/등수(1 또는 2) 크롤링 후 DB insert-or-ignore.
    반환: 삽입된 행 수(추정)
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    # 여러 URL 패턴을 순차 시도 (사이트 변경 대응)
    url_patterns = [
        # (A) 회차/등수/페이지 조합
        "https://dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={round}&rankNo={rank}&nowPage={page}",
        # (B) 회차/페이지 (동일 페이지 내 섹션 구분형)
        "https://dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={round}&nowPage={page}",
        # (C) 기본(최신) 페이지
        "https://dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&nowPage={page}",
    ]

    all_rows: List[Dict[str, Any]] = []
    empty_hits = 0

    # 1~10 페이지 정도 스캔
    for page in range(1, 10 + 1):
        page_got = 0
        tried_any = False

        for tmpl in url_patterns:
            url = tmpl.format(round=round_no, rank=rank, page=page)
            tried_any = True
            try:
                resp = session.get(url, timeout=12, allow_redirects=True)
            except Exception as e:
                print(f"[shops] req-error: {url} -> {e}")
                continue
            if resp.status_code != 200:
                # 다음 템플릿 시도
                continue

            html = _decode(resp)
            soup = BeautifulSoup(html, "lxml")

            tables = _tables_for_rank(soup, rank)
            if not tables:
                # 다음 템플릿 시도
                continue

            for t in tables:
                rows = _parse_table(t, round_no, rank, source_url=url)
                if rows:
                    all_rows.extend(rows)
                    page_got += len(rows)

            if page_got == 0:
                _dump(html, round_no, rank, page, "emptyrows")
            else:
                break  # 이 페이지에서 데이터 확보 → 다음 페이지로

        if not tried_any:
            break

        if page_got == 0:
            empty_hits += 1
            if empty_hits >= 2:
                break  # 연속 두 페이지 비면 중단
        else:
            empty_hits = 0

        time.sleep(0.35)

    # 혹시 잘못 섞인 데이터가 있으면 최종 필터
    all_rows = [r for r in all_rows if r.get("rank") == rank]

    # 중복 제거(최종)
    uniq: Dict[tuple, Dict[str, Any]] = {}
    for r in all_rows:
        key = (r["round"], r["rank"], r["name"], r["address"])
        if key not in uniq:
            uniq[key] = r
    dedup = list(uniq.values())

    inserted = _insert_many(dedup)
    print(f"[shops] round={round_no} rank={rank} -> rows={len(dedup)}")
    return inserted
