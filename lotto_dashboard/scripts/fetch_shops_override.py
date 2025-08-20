#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re, time, os
import requests
from bs4 import BeautifulSoup

# 차단 회피를 위한 기본 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://dhlottery.co.kr/store.do?method=topStore&pageGubun=L645",
    "Connection": "keep-alive",
}

DUMP_DIR = "logs/shops"
os.makedirs(DUMP_DIR, exist_ok=True)

def _save_dump(html: str, round_no: int, page: int, tag: str, reason: str):
    fn = f"{DUMP_DIR}/{tag}_{round_no}_p{page}_{int(time.time())}.html"
    try:
        with open(fn, "w", encoding="utf-8") as f:
            f.write(f"<!-- reason: {reason} -->\n")
            f.write(html)
        print(f"[dump] saved {fn}")
    except Exception as e:
        print(f"[dump:err] {e}")

def _decode_kr(resp: requests.Response) -> str:
    # 동행복권은 EUC-KR인 경우가 많음
    try:
        return resp.content.decode("euc-kr", errors="ignore")
    except Exception:
        try:
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except Exception:
            return resp.content.decode("utf-8", errors="ignore")

def _normalize_rank(raw):
    if raw is None:
        return None
    s = str(raw)
    m = re.search(r"(\d+)\s*등", s)
    if m:
        return int(m.group(1))
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None

def _clean(s):
    return (s or "").strip()

def _pick_table(soup: BeautifulSoup):
    # 1순위: class=tbl_data
    cand = soup.select_one("table.tbl_data")
    if cand: return cand
    # 2순위: 헤더에 키워드가 들어있는 테이블
    for t in soup.find_all("table"):
        headtxt = t.get_text(" ", strip=True)
        if any(k in headtxt for k in ("상호", "주소", "판매", "구분", "등수")):
            return t
    return None

def _header_index_map(table: BeautifulSoup):
    idx = {"rank": None, "name": None, "address": None, "method": None}
    thead = table.find("thead")
    if not thead:
        return idx
    ths = thead.find_all("th")
    for i, th in enumerate(ths):
        tx = th.get_text(strip=True)
        if any(k in tx for k in ("등", "순위", "구분")):
            idx["rank"] = i
        elif any(k in tx for k in ("상호", "상호명", "판매점", "점포", "가맹점")):
            idx["name"] = i
        elif any(k in tx for k in ("주소", "위치", "소재지")):
            idx["address"] = i
        elif any(k in tx for k in ("방법", "방식", "구입")):
            idx["method"] = i
    return idx

def fetch_shops(round_no: int):
    """
    동행복권 TopStore 회차별(1~2등) 판매점 파싱.
    반환: [{round, rank, name, address, method, lat=None, lon=None}, ...]
    """
    rows = []
    session = requests.Session()
    session.headers.update(HEADERS)

    URL_TMPL = "https://dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={round}&nowPage={page}"

    empty_pages = 0
    for page in range(1, 10):  # 1~9페이지 스캔
        url = URL_TMPL.format(page=page, round=round_no)
        try:
            resp = session.get(url, timeout=12, allow_redirects=True)
        except Exception as e:
            print(f"[shops] round={round_no} page={page} req-error: {e}")
            break
        if resp.status_code != 200:
            print(f"[shops] round={round_no} page={page} status={resp.status_code}")
            break

        html = _decode_kr(resp)
        soup = BeautifulSoup(html, "lxml")

        table = _pick_table(soup)
        if not table:
            _save_dump(html, round_no, page, "notable", "no-table")
            empty_pages += 1
            if empty_pages >= 2:
                break
            continue

        idx = _header_index_map(table)
        tbody = table.find("tbody") or table
        got = 0

        for tr in tbody.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 3:
                continue

            def _get(i): return _clean(tds[i].get_text()) if (0 <= i < len(tds)) else ""
            if all(v is None for v in idx.values()):
                # 위치 추정: [등수/구분, 상호, 주소, 방법] 순 배치가 흔함
                rank_txt = _get(0)
                name     = _get(1)
                address  = _get(2) if len(tds) >= 3 else ""
                method   = _get(3) if len(tds) >= 4 else ""
            else:
                rank_txt = _get(idx["rank"])    if idx["rank"]    is not None else _get(0)
                name     = _get(idx["name"])    if idx["name"]    is not None else _get(1)
                address  = _get(idx["address"]) if idx["address"] is not None else _get(2)
                method   = _get(idx["method"])  if idx["method"]  is not None else _get(3 if len(tds)>=4 else 2)

            # 잡음 방지
            if not name or len(name) > 200:
                continue
            if re.search(r"전체\s*지역\s*상호", name):
                continue

            rows.append({
                "round": round_no,
                "rank": _normalize_rank(rank_txt),
                "name": name,
                "address": address or None,
                "method": method or None,
                "lat": None,
                "lon": None,   # DB 컬럼은 lon (프런트는 lng로 매핑)
            })
            got += 1

        if got == 0:
            _save_dump(html, round_no, page, "emptyrows", "no-rows")

        if got == 0:
            empty_pages += 1
            if empty_pages >= 2:
                break
        else:
            empty_pages = 0

        time.sleep(0.35)

    return rows
