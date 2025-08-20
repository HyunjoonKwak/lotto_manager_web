import os, re, time
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

# -----------------------------------------
# 경로/상수/로그
# -----------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs", "shops")
os.makedirs(LOG_DIR, exist_ok=True)

BASE_URL = "https://dhlottery.co.kr/store.do"
COMMON = {"method": "topStore", "pageGubun": "L645"}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36",
    "Referer": "https://dhlottery.co.kr/",
}

VALID_METHODS = {"자동", "반자동", "수동"}
RANGE_RE  = re.compile(r"\b\d{1,4}\s*~\s*\d{1,4}\b")          # 601~1185
MASS_NUM  = re.compile(r"(?:\b\d{2,4}\b[ ,]*){15,}")          # 숫자 나열 덩어리

def _save(path: str, text: str):
    try:
        with open(path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(text or "")
    except Exception:
        pass

def _save_debug(name: str, round_no: int, rank: int, page: int, tag: str, text: str):
    fn = f"{name}_{round_no}_{rank}_p{page}_{tag}.debug.html"
    _save(os.path.join(LOG_DIR, fn), text or "")

# -----------------------------------------
# 요청 & 인코딩
# -----------------------------------------
def _request(round_no: int, rank: int, page: int) -> Optional[str]:
    """
    여러 파라미터 조합(nowPage/pgNo/pageNum/...)로 요청하고 EUC-KR 우선 디코딩
    """
    page_keys = ["nowPage", "pgNo", "pageNum", "currentPage", "pageIndex"]
    rank_keys = [{"rank": rank}, {"rankNo": rank}, {"winRank": rank}, {"grd": rank}, {}]

    s = requests.Session()
    for rk in rank_keys:
        for pk in page_keys:
            params = dict(COMMON)
            params.update({"drwNo": round_no})
            params.update(rk)
            params[pk] = page
            try:
                r = s.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
            except Exception:
                continue
            if r.status_code != 200:
                continue

            raw = r.content
            for enc in ("euc-kr", "cp949", "utf-8", r.apparent_encoding or "", "iso-8859-1"):
                if not enc:
                    continue
                try:
                    text = raw.decode(enc, errors="strict")
                    if page == 1:
                        _save_debug("shops", round_no, rank, page, f"raw_{enc.lower()}", text)
                    return text
                except Exception:
                    continue
            # 폴백
            text = r.text
            if page == 1:
                _save_debug("shops", round_no, rank, page, "raw_fallback", text)
            return text
    return None

# -----------------------------------------
# 파싱
# -----------------------------------------
def _clean(s: str) -> str:
    return (s or "").replace("\xa0", " ").strip()

def _select_table(soup: BeautifulSoup, round_no: int, rank: int, page: int, html: str) -> Optional[BeautifulSoup]:
    # 1순위
    t = soup.select_one("table.tbl_data")
    if t:
        _save_debug("table", round_no, rank, page, "tbl_data", str(t))
        return t
    # 2순위: 가장 '그럴듯'한 테이블 점수화
    best, best_score = None, -10**9
    for cand in soup.find_all("table"):
        head = cand.find("thead")
        headers = [th.get_text(strip=True) for th in head.find_all("th")] if head else []
        if not headers:
            first_tr = cand.find("tr")
            if first_tr:
                headers = [td.get_text(strip=True) for td in first_tr.find_all(["th","td"])]
        score = 0
        if any(("상호" in h) or ("상호명" in h) for h in headers): score += 6
        if any(("소재지" in h) or ("주소" in h) or ("위치" in h) for h in headers): score += 5
        if any(("판매구분" in h) or ("구분" in h) or ("방식" in h) for h in headers): score += 3
        if any(("번호" in h) or ("순위" in h) for h in headers): score += 2
        if any(RANGE_RE.search(h) or MASS_NUM.search(h) for h in headers): score -= 20
        if score > best_score:
            best, best_score = cand, score
    if best:
        _save_debug("table", round_no, rank, page, f"best_{best_score}", str(best))
    else:
        _save_debug("table", round_no, rank, page, "not_found", html)
    return best

def _parse_page(html: str, round_no: int, rank: int, page: int) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _select_table(soup, round_no, rank, page, html)
    if not table:
        return []

    # 헤더 파악(열 인덱스 매핑)
    head = table.find("thead")
    headers = [th.get_text(strip=True) for th in head.find_all("th")] if head else []
    name_idx = addr_idx = method_idx = count_idx = None

    for i, h in enumerate(headers):
        if ("상호" in h) or ("상호명" in h): name_idx = i
        if ("소재지" in h) or ("주소" in h) or ("위치" in h): addr_idx = i
        if ("판매구분" in h) or ("구분" in h) or ("방식" in h): method_idx = i
        if ("당첨횟수" in h): count_idx = i

    body = table.find("tbody") or table
    out: List[Dict] = []
    seen = set()
    for tr in body.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        values = [td.get_text(" ", strip=True) for td in tds]
        values = [v for v in values if v]

        # 헤더행/네비게이션 잡음 제거
        joined = " ".join(values)
        if ("상호" in joined and ("소재지" in joined or "주소" in joined)):
            continue
        if RANGE_RE.search(joined) or MASS_NUM.search(joined):
            continue

        def pick(idx: Optional[int], fallback: Optional[int] = None) -> str:
            if idx is not None and idx < len(values):
                return values[idx]
            if fallback is not None and fallback < len(values):
                return values[fallback]
            return ""

        name = _clean(pick(name_idx, 1 if values and values[0].isdigit() else 0))
        addr = _clean(pick(addr_idx, 2 if values and values[0].isdigit() else 1))
        method = _clean(pick(method_idx, 3 if values and values[0].isdigit() else 2))
        # 당첨횟수 케이스는 method가 없을 수 있음
        if not method and count_idx is not None and count_idx < len(values):
            # method 대신 "n회"로 표기(모델에는 별도 컬럼이 없으므로 참고용)
            method = f"{values[count_idx]}회" if values[count_idx].isdigit() else method

        if not name and not addr:
            continue

        # 판매구분 정제
        if method and method not in VALID_METHODS and not method.endswith("회"):
            a = tr.find("a")
            if a:
                atxt = _clean(a.get_text(" ", strip=True))
                if atxt in VALID_METHODS:
                    method = atxt
        if rank == 1 and not method:
            method = "미상"

        key = (name, addr, method)
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "round": round_no,
            "rank": rank,
            "name": name,
            "address": addr,
            "method": method,
        })
    return out

# -----------------------------------------
# 공개 함수
# -----------------------------------------
def fetch_shops_page(round_no: int, rank: int, page: int = 1) -> List[Dict]:
    html = _request(round_no, rank, page)
    if html is None:
        return []
    rows = _parse_page(html, round_no, rank, page)
    if not rows:
        _save_debug("shops", round_no, rank, page, "empty_or_noise", html)
    return rows

def fetch_shops_all_pages(round_no: int, rank: int = 1, max_pages: int = 30, sleep_sec: float = 0.2) -> List[Dict]:
    all_rows: List[Dict] = []
    seen = set()
    for p in range(1, max_pages + 1):
        rows = fetch_shops_page(round_no, rank, p)
        if not rows:
            if p == 1:
                continue
            break
        for r in rows:
            key = (r["round"], r["rank"], r["name"], r.get("address",""))
            if key in seen:
                continue
            seen.add(key)
            all_rows.append(r)
        time.sleep(sleep_sec)

    if not all_rows:
        html = _request(round_no, rank, 1)
        if html:
            _save_debug("shops", round_no, rank, 0, "no_results", html)
    return all_rows
