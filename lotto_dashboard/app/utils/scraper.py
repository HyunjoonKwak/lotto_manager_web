import time, os, re
from typing import Dict, List, Optional, Tuple
import requests
import requests_cache
from bs4 import BeautifulSoup

# --------------------------
# 경로/캐시/상수
# --------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs", "shops")
os.makedirs(LOG_DIR, exist_ok=True)

CACHE_PATH = os.path.join(PROJECT_ROOT, "logs", "http_cache")
session = requests_cache.CachedSession(
    cache_name=CACHE_PATH, backend="sqlite", expire_after=24*3600,
    fast_save=True, timeout=30,
)

LOTTO_DRAW_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drwNo}"
LOTTO_SHOP_BASE = "https://www.dhlottery.co.kr/store.do"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36",
    "Referer": "https://www.dhlottery.co.kr/"
}

VALID_METHODS = {"자동", "반자동", "수동"}
ROUND_RANGE_RE = re.compile(r"\b\d{1,4}\s*~\s*\d{1,4}\b")
MASS_DIGIT_RE  = re.compile(r"(?:\b\d{2,4}\b[ ,]*){10,}")  # 숫자 나열 과다

# --------------------------
# 로그 유틸
# --------------------------
def _save_debug_html(html: str, round_no: int, rank: int, page: int, tag: str = "") -> str:
    suffix = f"_{tag}" if tag else ""
    filename = f"shops_{round_no}_{rank}_p{page}{suffix}.debug.html"
    path = os.path.join(LOG_DIR, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html or "")
    except Exception:
        pass
    return path

def _save_debug_snippet(soup: BeautifulSoup, round_no: int, rank: int, page: int, tag: str):
    """선택된 테이블만 따로 저장(문제 테이블 진단용)"""
    try:
        html = str(soup)
        _save_debug_html(html, round_no, rank, page, tag=tag)
    except Exception:
        pass

# --------------------------
# 기본 추첨 정보
# --------------------------
def fetch_draw(drw_no: int) -> Optional[Dict]:
    url = LOTTO_DRAW_URL.format(drwNo=drw_no)
    r = session.get(url, headers=HEADERS, timeout=15)
    data = r.json()
    if data.get("returnValue") != "success":
        return None
    return {
        "round": data.get("drwNo"),
        "draw_date": data.get("drwNoDate"),
        "numbers": [data.get(f"drwtNo{i}") for i in range(1,7)],
        "bonus": data.get("bnusNo"),
    }

# --------------------------
# 당첨점 파싱 핵심
# --------------------------
def _detect_page_rank(html: str) -> Optional[int]:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    if re.search(r"\b2\s*등\b", text):
        return 2
    if re.search(r"\b1\s*등\b", text):
        return 1
    return None

def _clean_text(s: str) -> str:
    return (s or "").replace("\xa0", " ").strip()

def _looks_like_noise(name: str, address: str, raw_html: str, a_count: int) -> bool:
    """페이지네이션/필터/헤더/숫자나열 노이즈 감지"""
    text = f"{name} {address}".strip()
    if not text:
        return True
    if "전체 지역" in text and "상호" in text:
        return True
    if ROUND_RANGE_RE.search(text):
        return True
    if MASS_DIGIT_RE.search(text):
        return True
    if a_count >= 10:  # 링크가 잔뜩이면 페이지네이션 블록일 확률 높음
        return True
    # 테이블 헤더류
    if name in ("상호", "상호명") or address in ("소재지", "주소", "위치"):
        return True
    # 행 HTML 자체가 숫자 덩어리(혹은 옵션 목록)일 때
    if MASS_DIGIT_RE.search(raw_html):
        return True
    return False

def _score_headers(headers: List[str]) -> int:
    score = 0
    has_num = any("번호" in h for h in headers)
    has_name = any(h.find("상호") >= 0 for h in headers)
    has_addr = any(h.find("소재지") >= 0 or h.find("주소") >= 0 or h.find("위치") >= 0 for h in headers)
    has_method = any(h.find("구분") >= 0 or h.find("판매구분") >= 0 or h.find("방식") >= 0 for h in headers)
    if has_num: score += 5
    if has_name: score += 5
    if has_addr: score += 3
    if has_method: score += 2
    # 숫자 나열 헤더 감점
    for h in headers:
        if MASS_DIGIT_RE.search(h):
            score -= 10
    return score

def _select_best_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    candidates = soup.find_all("table")
    best, best_score = None, -10**9
    for t in candidates:
        head = t.find("thead")
        if head:
            headers = [th.get_text(strip=True) for th in head.find_all("th")]
        else:
            # thead가 없으면 첫 tr을 헤더처럼 봄
            first_tr = t.find("tr")
            headers = [td.get_text(strip=True) for td in first_tr.find_all(["th", "td"])] if first_tr else []
        sc = _score_headers(headers)
        if sc > best_score:
            best, best_score = t, sc
    return best

def _parse_shop_table(html: str, round_no: int, expected_rank: int) -> Tuple[List[Dict], Optional[int], int]:
    soup = BeautifulSoup(html, "html.parser")
    page_rank = _detect_page_rank(html)

    table = soup.select_one("table.tbl_data") or _select_best_table(soup)
    if not table:
        return [], page_rank, 0

    # 본문 추출
    body = table.find("tbody") or table
    trs = body.find_all("tr")
    rows: List[Dict] = []
    examined = 0

    for tr in trs:
        tds = tr.find_all("td")
        if not tds:
            continue
        examined += 1
        texts = [td.get_text(" ", strip=True) for td in tds]
        texts = [t for t in texts if t]
        raw_html = str(tr)
        a_count = len(tr.find_all("a"))

        # 일반 패턴: [번호, 상호명, 소재지, 구분]
        rank, name, address, method = None, "", "", ""
        if texts and texts[0].isdigit():
            try:
                rank = int(texts[0])
            except:
                rank = None
            if len(texts) >= 2: name = texts[1]
            if len(texts) >= 3: address = texts[2]
            if len(texts) >= 4: method  = texts[3]
        else:
            if len(texts) >= 1: name = texts[0]
            if len(texts) >= 2: address = texts[1]
            if len(texts) >= 3: method  = texts[2]

        name = _clean_text(name)
        address = _clean_text(address)
        method = _clean_text(method)

        # 노이즈 제거 (페이지네이션/필터/헤더)
        if _looks_like_noise(name, address, raw_html, a_count):
            continue

        row_rank = rank if rank is not None else (page_rank if page_rank is not None else expected_rank)
        if row_rank != expected_rank:
            continue

        # method 정제
        if method not in VALID_METHODS:
            a = tr.find("a")
            if a:
                atxt = _clean_text(a.get_text(" ", strip=True))
                if atxt in VALID_METHODS:
                    method = atxt
            if not method and (page_rank == 1 or expected_rank == 1):
                method = "미상"

        rows.append({
            "round": round_no,
            "rank": row_rank,
            "name": name,
            "address": address,
            "method": method,
        })

    return rows, page_rank, examined

def _build_shop_params(round_no: int, page: int, rank: int) -> List[Dict]:
    bases = []
    bases.append({"method": "topStore", "pageGubun": "L645", "rank": rank, "drwNo": round_no})
    bases.append({"method": "topStore", "pageGubun": "L645", "drwNo": round_no})
    bases.append({"method": "topStore", "pageGubun": "L645", "winRank": rank, "drwNo": round_no})
    bases.append({"method": "topStore", "pageGubun": "L645", "grd": rank, "drwNo": round_no})

    page_keys = ["pageNum", "nowPage", "currentPage", "pageIndex", "pgNo"]
    params_list: List[Dict] = []
    for base in bases:
        for pk in page_keys:
            d = dict(base); d[pk] = page
            params_list.append(d)
    params_list.append(bases[0])
    params_list.append(bases[1])
    return params_list

def fetch_shops_all_pages(drw_no: int, rank: int = 1, max_pages: int = 20, sleep_sec: float = 0.2) -> List[Dict]:
    all_rows: List[Dict] = []
    seen = set()
    last_detected_rank: Optional[int] = None
    last_response_text: Optional[str] = None

    for page in range(1, max_pages+1):
        page_rows: List[Dict] = []
        response_text_for_debug = None

        for params in _build_shop_params(drw_no, page, rank):
            r = session.get(LOTTO_SHOP_BASE, params=params, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                continue
            response_text_for_debug = r.text
            last_response_text = r.text  # 마지막 응답 보관

            rows, page_rank, examined = _parse_shop_table(r.text, drw_no, expected_rank=rank)
            if page_rank is not None:
                last_detected_rank = page_rank
            if rows:
                page_rows = rows
                break

        # 요청 랭크와 페이지 랭크가 다르면(예: 2등 페이지) → 저장 후 중단
        if last_detected_rank is not None and last_detected_rank != rank:
            if response_text_for_debug:
                _save_debug_html(response_text_for_debug, drw_no, rank, page, tag="rank_mismatch")
            break

        if not page_rows:
            # 행이 하나도 안 나왔으면 저장
            if response_text_for_debug:
                _save_debug_html(response_text_for_debug, drw_no, rank, page, tag="empty_page")
            if page == 1:
                continue
            else:
                break
        else:
            # 행이 있더라도 모두 노이즈 제거된 결과일 수 있음 → 너무 적으면 스니펫 저장
            if len(page_rows) < 1 and response_text_for_debug:
                _save_debug_html(response_text_for_debug, drwNo, rank, page, tag="only_noise")

        # 누적(중복제거)
        for row in page_rows:
            key = (row["round"], row["name"], row.get("address",""), row.get("method",""))
            if key not in seen:
                seen.add(key)
                all_rows.append(row)

        time.sleep(sleep_sec)

    if not all_rows and last_response_text:
        _save_debug_html(last_response_text, drw_no, rank, 0, tag="no_results")

    return all_rows

# 과거 호환
def fetch_shops(drw_no: int) -> List[Dict]:
    return fetch_shops_all_pages(drw_no, rank=1, max_pages=20)

def iter_fetch_draws(start: int, stop_if_missing: int = 3, sleep_sec: float = 0.2):
    misses = 0
    cur = start
    while True:
        d = fetch_draw(cur)
        if d:
            misses = 0
            yield d
        else:
            misses += 1
            if misses >= stop_if_missing:
                break
        cur += 1
        time.sleep(sleep_sec)
