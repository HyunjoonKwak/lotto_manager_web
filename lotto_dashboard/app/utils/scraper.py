import time, os, re, json, logging
from typing import Dict, List, Optional, Tuple
import requests
import requests_cache
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --------------------------
# 경로/캐시/상수
# --------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs", "shops")
os.makedirs(LOG_DIR, exist_ok=True)

CACHE_PATH = os.path.join(PROJECT_ROOT, "logs", "http_cache")

HOME = "https://www.dhlottery.co.kr/"
HOME_BYWIN = "https://www.dhlottery.co.kr/gameResult.do?method=byWin"

LOTTO_DRAW_URL  = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drwNo}"
LOTTO_DRAW_HTML = "https://www.dhlottery.co.kr/gameResult.do?method=byWin&drwNo={drwNo}"
LOTTO_SHOP_BASE = "https://www.dhlottery.co.kr/store.do"

VALID_METHODS = {"자동", "반자동", "수동"}
ROUND_RANGE_RE = re.compile(r"\b\d{1,4}\s*~\s*\d{1,4}\b")
MASS_DIGIT_RE  = re.compile(r"(?:\b\d{2,4}\b[ ,]*){10,}")  # 숫자 나열 과다

log = logging.getLogger(__name__)

# --------------------------
# 세션: 브라우저 흉내 + 재시도
# --------------------------
def _new_browser_session():
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return s

# 전역 단일 브라우저 세션 (쿠키 공유)
browser = _new_browser_session()

# HTML(당첨점/결과 페이지)용 캐시 세션
session_cached = requests_cache.CachedSession(
    cache_name=CACHE_PATH, backend="sqlite", expire_after=24*3600,
    allowable_methods=["GET", "HEAD"], allowable_codes=[200],
    stale_if_error=True,
    fast_save=True,
    timeout=30,
)
session_cached.headers.update({
    "User-Agent": browser.headers.get("User-Agent"),
    "Referer": HOME,
})

def prime_cookies():
    """쿠키/세션 프라임: 홈 → byWin → 홈 순으로 살짝 두드림"""
    try:
        browser.get(HOME, timeout=10, allow_redirects=True)
        time.sleep(0.3)
        browser.get(HOME_BYWIN, timeout=10, allow_redirects=True, headers={"Referer": HOME})
        time.sleep(0.3)
        browser.get(HOME, timeout=10, allow_redirects=True)
    except Exception as e:
        log.debug("prime_cookies error: %s", e)

# --------------------------
# 디버그 저장
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

def _save_debug_text(text: str, name: str):
    path = os.path.join(LOG_DIR, f"{name}.debug.html")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text or "")
    except Exception:
        pass
    return path

# --------------------------
# 점검(maintenance) 감지
# --------------------------
def _is_maintenance_page(html: str) -> bool:
    """동행복권 점검/안내/차단 페이지 간단 감지"""
    if not html:
        return False
    text = html[:2000]  # 앞부분만 훑어도 충분
    keywords = [
        "시스템 점검", "점검중", "점검 중", "점검시간", "서비스 이용이 원활하지",
        "접근이 제한", "보안", "안내 페이지", "일시 중단", "오류가 발생",
    ]
    return any(kw in text for kw in keywords)

# --------------------------
# HTML 폴백 파서 (회차 결과 페이지)
# --------------------------
def _parse_draw_from_html(html: str, drw_no: int) -> Optional[Dict]:
    """
    결과 페이지(HTML)에서 당첨번호/보너스/날짜 추출
    우선순위:
      1) id 기반: #drwtNo1..#drwtNo6, #bnusNo
      2) 클래스 기반: .ball_645 (7개 나오면 마지막을 보너스로 간주)
    날짜:
      .win_result 등 텍스트에서 YYYY-MM-DD 또는 YYYY.MM.DD
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- 번호 6개: id 기반
    nums: List[int] = []
    for i in range(1, 7):
        el = soup.select_one(f"#drwtNo{i}")
        if el and el.get_text(strip=True).isdigit():
            nums.append(int(el.get_text(strip=True)))
        else:
            nums = []
            break

    bonus: Optional[int] = None

    # --- 클래스 기반 보강 (모바일/변형 레이아웃)
    if not nums:
        balls = [b.get_text(strip=True) for b in soup.select(".ball_645")]
        balls = [int(x) for x in balls if x.isdigit()]
        if len(balls) >= 7:
            nums = balls[:6]
            bonus = balls[6]
        elif len(balls) >= 6:
            nums = balls[:6]

    if not nums or len(nums) < 6:
        return None

    # --- 보너스: id 기반 우선
    if bonus is None:
        b_el = soup.select_one("#bnusNo")
        if b_el and b_el.get_text(strip=True).isdigit():
            bonus = int(b_el.get_text(strip=True))

    # 날짜
    draw_date = None
    for sel in [".win_result", ".lottery_win_number", "body"]:
        wr = soup.select_one(sel)
        if not wr:
            continue
        t = wr.get_text(" ", strip=True)
        m = re.search(r"\d{4}\.\d{2}\.\d{2}|\d{4}-\d{2}-\d{2}", t)
        if m:
            draw_date = m.group(0).replace(".", "-")
            break

    return {
        "round": drw_no,
        "draw_date": draw_date,
        "numbers": nums,
        "bonus": bonus if bonus is not None else 0,
    }

# --------------------------
# 기본 추첨 정보 (JSON 우선, 실패 시 HTML 폴백 + 점검 감지)
# --------------------------
def fetch_draw(drw_no: int) -> Optional[Dict]:
    # 최초 한 번 쿠키 프라임
    if not getattr(fetch_draw, "_primed", False):
        prime_cookies()
        fetch_draw._primed = True

    # 1) JSON 엔드포인트 먼저 시도 (AJAX 헤더 부여)
    url = LOTTO_DRAW_URL.format(drwNo=drw_no)
    try:
        r = browser.get(url, timeout=10, headers={
            "Accept": "application/json, text/javascript, */*; q=0.1",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": HOME_BYWIN,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })
    except requests.RequestException as e:
        log.warning("[fetch_draw] round=%s request error: %s", drw_no, e)
        r = None

    if r is not None and r.status_code == 200:
        ctype = r.headers.get("Content-Type", "")
        text_head = (r.text or "")[:200].strip()
        if "application/json" in ctype or text_head.startswith("{"):
            try:
                jd = r.json()
            except json.JSONDecodeError:
                jd = None
            if jd and jd.get("returnValue") == "success":
                return {
                    "round": jd.get("drwNo"),
                    "draw_date": jd.get("drwNoDate"),
                    "numbers": [jd.get(f"drwtNo{i}") for i in range(1, 7)],
                    "bonus": jd.get("bnusNo") or 0,
                }
            else:
                log.warning("[fetch_draw] round=%s JSON but invalid payload", drw_no)
        else:
            # JSON이 아닌 HTML이면 점검페이지인지 검사
            if _is_maintenance_page(r.text):
                _save_debug_html(r.text, drw_no, 0, 0, tag="maintenance_json")
                log.warning("[fetch_draw] round=%s maintenance detected on JSON endpoint", drw_no)
                return None
            log.warning("[fetch_draw] round=%s non-JSON: ctype=%r head=%r", drw_no, ctype, text_head)
    elif r is not None:
        log.warning("[fetch_draw] round=%s bad status=%s", drw_no, r.status_code)

    # 2) JSON 실패 시 HTML 페이지 폴백
    html_url = LOTTO_DRAW_HTML.format(drwNo=drw_no)
    try:
        r2 = browser.get(html_url, timeout=10, headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": HOME_BYWIN,
        })
    except requests.RequestException as e:
        log.warning("[fetch_draw][fallback] round=%s request error: %s", drw_no, e)
        return None

    if r2.status_code != 200:
        log.warning("[fetch_draw][fallback] round=%s bad status=%s", drw_no, r2.status_code)
        return None

    # 점검/안내 페이지 감지 → 디버그 저장 후 None
    if _is_maintenance_page(r2.text):
        _save_debug_html(r2.text, drw_no, 0, 0, tag="maintenance_html")
        log.warning("[fetch_draw][fallback] round=%s maintenance detected on HTML page", drw_no)
        return None

    parsed = _parse_draw_from_html(r2.text, drw_no)
    if not parsed:
        _save_debug_html(r2.text, drw_no, 0, 0, tag="parse_failed")
        log.warning("[fetch_draw][fallback] round=%s parse failed (HTML)", drw_no)
        return None
    return parsed

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
    text = f"{name} {address}".strip()
    if not text:
        return True
    if "전체 지역" in text and "상호" in text:
        return True
    if ROUND_RANGE_RE.search(text):
        return True
    if MASS_DIGIT_RE.search(text):
        return True
    if a_count >= 10:
        return True
    if name in ("상호", "상호명") or address in ("소재지", "주소", "위치"):
        return True
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

        if _looks_like_noise(name, address, raw_html, a_count):
            continue

        row_rank = rank if rank is not None else (page_rank if page_rank is not None else expected_rank)
        if row_rank != expected_rank:
            continue

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
            r = session_cached.get(LOTTO_SHOP_BASE, params=params, timeout=20)
            if r.status_code != 200:
                continue

            # 점검/안내 페이지 감지 → 저장 & 중단
            if _is_maintenance_page(r.text):
                _save_debug_html(r.text, drw_no, rank, page, tag="maintenance_shops")
                log.warning("[fetch_shops] round=%s page=%s maintenance detected", drw_no, page)
                return []  # 바로 종료

            response_text_for_debug = r.text
            last_response_text = r.text

            rows, page_rank, examined = _parse_shop_table(r.text, drw_no, expected_rank=rank)
            if page_rank is not None:
                last_detected_rank = page_rank
            if rows:
                page_rows = rows
                break

        if last_detected_rank is not None and last_detected_rank != rank:
            if response_text_for_debug:
                _save_debug_html(response_text_for_debug, drw_no, rank, page, tag="rank_mismatch")
            break

        if not page_rows:
            if response_text_for_debug:
                _save_debug_html(response_text_for_debug, drw_no, rank, page, tag="empty_page")
            if page == 1:
                continue
            else:
                break
        else:
            if len(page_rows) < 1 and response_text_for_debug:
                _save_debug_html(response_text_for_debug, drw_no, rank, page, tag="only_noise")

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

def iter_fetch_draws(start: int, stop_if_missing: int = 3, sleep_sec: float = 0.6):
    misses = 0
    cur = start
    # 최초 루프 시작 전에 한 번 프라임(안정성)
    prime_cookies()
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
