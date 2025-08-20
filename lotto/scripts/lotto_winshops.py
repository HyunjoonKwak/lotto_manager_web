# -*- coding: utf-8 -*-
"""
lotto_winshops.py
- 동행복권 회차별 1등 판매점(로또 6/45) 파서
- Python 3.8 호환 (typing: List/Dict/Tuple 사용)
"""

from __future__ import annotations
import re
import time
from typing import List, Dict, Tuple, Optional

import requests
from bs4 import BeautifulSoup


# ---- HTTP 설정 --------------------------------------------------------------

BASE_URL = "https://dhlottery.co.kr/gameResult.do?method=byWin&drwNo={draw_no}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Synology) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome Safari"
    )
}

TIMEOUT = 8  # seconds
RETRY = 2    # 네트워크 순간 장애 대비 소규모 재시도


# ---- 유틸 -------------------------------------------------------------------

_ws_re = re.compile(r"\s+", re.UNICODE)


def _clean(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = _ws_re.sub(" ", s.strip())
    return s or None


def _get(url: str) -> str:
    """
    GET with EUC-KR 강제 인코딩 & 소규모 재시도
    """
    last_err = None
    for i in range(RETRY + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            # 동행복권은 EUC-KR 메타. requests가 간혹 추정을 틀릴 수 있어 강제 지정.
            r.encoding = "euc-kr"
            # 일부 WAF/캐시 상황에서 빈 응답이 올 수 있으니 방어
            if not r.text or "<html" not in r.text.lower():
                raise ValueError("empty or invalid html")
            return r.text
        except Exception as e:
            last_err = e
            if i < RETRY:
                time.sleep(0.6)
            else:
                raise last_err
    # 여긴 사실상 도달하지 않음
    return ""


# ---- 파서 (1등 섹션만 안전 추출) -------------------------------------------

def _parse_first_prize_shops(html: str) -> List[Dict]:
    """
    페이지에서 '1등' 판매점 섹션만 골라서 파싱한다.
    - 동행복권 byWin 페이지는 '1등' / '2등' 섹션이 같은 CSS(class)로 반복될 수 있음
    - 그래서 '1등' 제목(h4 등)을 먼저 찾고, 그 다음 나오는 ul.list_topstore만 사용
    """
    soup = BeautifulSoup(html, "lxml")

    # 1) '1등'이 들어간 제목 후보들을 찾는다.
    #    h3/h4/div 등 다양한 태그일 수 있어서 텍스트 기반 탐색
    headings = []
    for tag_name in ("h2", "h3", "h4", "div", "p", "span"):
        for t in soup.find_all(tag_name):
            txt = t.get_text(" ", strip=True)
            if "1등" in txt:
                headings.append(t)

    ul = None

    # 2) 제목 후보에서 가장 가까운 다음 형제/자손 중 ul.list_topstore 를 찾는다.
    for h in headings:
        # (a) 형제 방향으로 먼저 탐색
        nxt = h.find_next(lambda x: x.name == "ul" and "list_topstore" in (x.get("class") or []))
        if nxt:
            ul = nxt
            break
        # (b) 자손 쪽에 있을 수도 있으니 한 번 더 탐색
        ins = h.find(lambda x: x.name == "ul" and "list_topstore" in (x.get("class") or []))
        if ins:
            ul = ins
            break

    # 3) 여전히 못찾으면, 가장 첫 번째 ul.list_topstore를 fallback으로 사용
    if not ul:
        uls = soup.select("ul.list_topstore")
        if uls:
            ul = uls[0]
        else:
            return []

    items: List[Dict] = []
    for li in ul.select("li"):
        # 많은 변형을 고려해 가능한 안정적인 셀렉터 우선
        name_el = li.select_one(".store_name")
        addr_el = li.select_one(".store_addr")
        info_el = li.select_one(".store_info")

        shop = _clean(name_el.get_text(strip=True)) if name_el else None
        address = _clean(addr_el.get_text(" ", strip=True)) if addr_el else None

        # 방법(자동/수동/반자동) 추정
        method = None
        if info_el:
            info_text = info_el.get_text(" ", strip=True)
            if "자동" in info_text:
                method = "자동"
            elif "수동" in info_text:
                method = "수동"
            elif "반자동" in info_text:
                method = "반자동"

        # 노이즈 제거: 완전히 빈 항목은 건너뛴다
        if not (shop or address):
            continue

        items.append(
            {
                "rank": 1,
                "shop": shop,
                "method": method,
                "address": address,
            }
        )

    return items


# ---- 공개 API ---------------------------------------------------------------

def fetch_winshops_by_draw(draw_no: int) -> List[Dict]:
    """
    주어진 회차(draw_no)의 1등 판매점 리스트를 반환한다.
    """
    url = BASE_URL.format(draw_no=draw_no)
    html = _get(url)
    return _parse_first_prize_shops(html)


def fetch_latest_winshops() -> Tuple[int, List[Dict]]:
    """
    DB 최신 회차를 읽어와 해당 회차의 1등 판매점을 반환한다.
    - 웹앱이 같은 디렉토리의 db.get_connection()을 제공한다고 가정
    """
    from db import get_connection  # 지역 import (도구 분리/테스트 편의)

    latest = 0
    with get_connection() as con:
        cur = con.cursor()
        cur.execute("SELECT MAX(draw_no) FROM lotto_results")
        row = cur.fetchone()
        latest = int(row[0] or 0)

    shops = fetch_winshops_by_draw(latest) if latest else []
    return latest, shops


# ---- CLI 테스트 -------------------------------------------------------------

def _pretty(items: List[Dict]) -> str:
    lines = []
    for it in items:
        lines.append(
            f"- {it.get('shop') or '(이름없음)'} | {it.get('method') or '-'} | {it.get('address') or '-'}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse, json, sys

    ap = argparse.ArgumentParser(description="Fetch 1st prize winshops from dhlottery.")
    ap.add_argument("--draw", type=int, help="회차 번호 (예: 1185). 생략하면 DB 최신 회차 사용.")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    if args.draw:
        shops = fetch_winshops_by_draw(args.draw)
        if args.json:
            print(json.dumps({"draw_no": args.draw, "count": len(shops), "shops": shops}, ensure_ascii=False, indent=2))
        else:
            print(f"[{args.draw}] 1등 판매점 {len(shops)}곳")
            print(_pretty(shops))
    else:
        latest, shops = fetch_latest_winshops()
        if args.json:
            print(json.dumps({"draw_no": latest, "count": len(shops), "shops": shops}, ensure_ascii=False, indent=2))
        else:
            print(f"[latest={latest}] 1등 판매점 {len(shops)}곳")
            print(_pretty(shops))
