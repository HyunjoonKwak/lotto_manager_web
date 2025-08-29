from __future__ import annotations
import os, re, json
from typing import List, Dict
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed

UA = os.environ.get("HTTP_USER_AGENT", "Mozilla/5.0")
HDRS = {"User-Agent": UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}

NUMBERS_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round}"
SHOPS_URL = "https://www.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={round}"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_numbers(round_: int) -> Dict:
    url = NUMBERS_URL.format(round=round_)
    r = requests.get(url, headers=HDRS, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data or data.get("returnValue") != "success":
        raise RuntimeError(f"Numbers API failed for round {round_}")
    return data

def parse_numbers(data: Dict):
    draw_date = data.get("drwNoDate")
    nums = [data.get(f"drwtNo{i}") for i in range(1,7)]
    bonus = data.get("bnusNo")
    if None in nums or bonus is None:
        raise ValueError("Incomplete numbers payload")
    return draw_date, nums, bonus

@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def fetch_shops_html(round_: int) -> str:
    url = SHOPS_URL.format(round=round_)
    r = requests.get(url, headers=HDRS, timeout=10)
    r.raise_for_status()
    return r.text

def _norm(s: str|None) -> str:
    return (s or "").strip()

def parse_shops(html: str, round_: int) -> List[Dict]:
    """
    테이블 헤더(TH)의 텍스트로 컬럼 인덱스를 식별해
    상호명(name) / 소재지(address) / 구분(type)을 정확히 추출합니다.
    헤더가 없거나 구조가 달라지면 보조 휴리스틱으로 보정합니다.
    """
    soup = BeautifulSoup(html, "lxml")
    results: List[Dict] = []

    def parse_table(tbl) -> List[Dict]:
        # 1) 헤더 인덱스 매핑 시도
        ths = [th.get_text(" ", strip=True) for th in tbl.find_all("th")]
        idx_name = idx_addr = idx_type = None

        # 대표 헤더 후보들
        for i, t in enumerate(ths):
            if re.search(r"(상호명|점포명|상호|배출점)", t):
                idx_name = i
            if re.search(r"(소재지|주소)", t):
                idx_addr = i
            if re.search(r"(구분|방식)", t):
                idx_type = i

        rows: List[Dict] = []
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            cells = [td.get_text(" ", strip=True) for td in tds]

            name = addr = typ = None

            # 2) 헤더 기반 매핑
            def by_index(idx):
                if idx is None: return None
                if 0 <= idx < len(cells):
                    return cells[idx]
                return None

            name = by_index(idx_name)
            addr = by_index(idx_addr)
            typ  = by_index(idx_type)

            # 3) 보조 휴리스틱 (헤더가 없거나 인덱스가 틀릴 때)
            if not name:
                a = tr.find("a")
                if a and a.get_text(strip=True):
                    name = a.get_text(strip=True)

            # 주소 후보(시/구/동/로/길 등 지명 키워드 포함) 중 가장 그럴싸한 것
            if not addr:
                cand = [c for c in cells if re.search(r"(시|군|구|동|로|길|도|읍|면)", c)]
                if cand:
                    # 너무 짧은 값(예: '자동')은 제외
                    cand = [c for c in cand if not re.fullmatch(r"(자동|수동|반자동)", c)]
                    if cand:
                        # 가장 긴 걸 채택
                        addr = max(cand, key=len)

            # 구분(자동/수동/반자동) 탐지
            if not typ:
                for c in cells:
                    if re.fullmatch(r"(자동|수동|반자동)", c):
                        typ = c
                        break

            # 만약 컬럼 순서가 [상호명, 구분, 소재지]였으면,
            # 흔히 name=cells[1], addr=cells[2]로 잘못 들어가는 케이스를 보정
            if not addr and len(cells) >= 3:
                # 가장 그럴싸한 주소 후보: 공백/숫자/한글이 섞인 긴 셀
                candidates = sorted(cells, key=len, reverse=True)
                for c in candidates:
                    if len(c) >= 6 and not re.fullmatch(r"(자동|수동|반자동)", c):
                        addr = c; break

            if name:
                rows.append({
                    "name": _norm(name),
                    "address": _norm(addr),
                    "type": _norm(typ) or None,
                    "lat": None, "lon": None,
                    "source_url": SHOPS_URL.format(round=round_),
                })
        return rows

    # 당첨점 테이블 후보 선택
    tables = []
    for tbl in soup.find_all("table"):
        th_texts = " ".join(th.get_text(strip=True) for th in tbl.find_all("th"))
        if any(k in th_texts for k in ("상호명", "점포명", "배출점", "소재지", "구분", "방식")):
            tables.append(tbl)

    for tbl in tables:
        results.extend(parse_table(tbl))

    # 중복 제거 (상호명+주소)
    uniq = {}
    for r in results:
        key = (r["name"], r.get("address") or "")
        uniq[key] = r
    return list(uniq.values())
