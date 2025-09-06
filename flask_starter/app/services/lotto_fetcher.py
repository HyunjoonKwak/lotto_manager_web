from datetime import datetime
from typing import Iterable, Callable, TypeVar, Optional, List, Dict
import time
import socket

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# DNS 설정 최적화 (한국 DNS 서버 사용)
try:
    import dns.resolver
    resolver = dns.resolver.Resolver()
    resolver.nameservers = ['8.8.8.8', '168.126.63.1', '168.126.63.2']  # Google DNS + KT DNS
except ImportError:
    pass

NUMBERS_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round}"
SHOPS_URL = "https://www.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={round}"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}
# 연결 타임아웃과 읽기 타임아웃을 분리
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 30

T = TypeVar("T")

# 전역 세션 변수 (재사용을 위해)
_global_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """전역 세션 반환 (없으면 생성)"""
    global _global_session
    if _global_session is None:
        _global_session = _create_session()
    return _global_session


def _create_session() -> requests.Session:
    """안정적인 HTTP 세션 생성"""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    
    # urllib3 레벨에서 재시도 전략 설정
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session


def _with_retries(fn: Callable[[], T], retries: int = 5, delay: float = 2.0) -> T:
    """재시도 로직 - 지수 백오프와 지연 시간 포함"""
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            return fn()
        except Exception as exc:  # network or parse errors
            last_exc = exc
            if attempt < retries - 1:  # 마지막 시도가 아닌 경우만 대기
                wait_time = delay * (2 ** attempt)  # 지수 백오프
                print(f"재시도 {attempt + 1}/{retries} 실패, {wait_time:.1f}초 후 재시도: {str(exc)}")
                time.sleep(wait_time)
            else:
                print(f"모든 재시도 실패: {str(exc)}")
    assert last_exc is not None
    raise last_exc


def fetch_draw(round_no: int) -> Dict:
    """Fetch lotto draw info by round. Replace URL/parsing with real source later."""
    # Example placeholder using official API-like JSON endpoint if available.
    # Here we structure a mock example for wiring. Replace with actual endpoint.
    url = NUMBERS_URL.format(round=round_no)
    def _req() -> Dict:
        # 전역 세션 재사용
        session = get_session()
        # (연결 타임아웃, 읽기 타임아웃) 튜플로 지정
        resp = session.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.raise_for_status()
        return resp.json()

    data = _with_retries(_req)
    if data.get("returnValue") != "success":
        raise ValueError("Invalid round or API response")
    numbers = [data[f"drwtNo{i}"] for i in range(1, 7)]
    bonus = data["bnusNo"]
    draw_date = datetime.strptime(data["drwNoDate"], "%Y-%m-%d").date()
    return {
        "round": round_no,
        "draw_date": draw_date,
        "numbers": numbers,
        "bonus": bonus,
    }


def fetch_winning_shops(round_no: int) -> List[Dict]:
    """Fetch 1st/2nd winning shops by scraping with pagination support.

    Note: This HTML structure may change; adjust selectors accordingly.
    2nd rank shops may span multiple pages using nowPage parameter.
    """
    try:
        result: List[Dict] = []

        # First, get page 1 to parse 1st rank shops and first page of 2nd rank
        url = SHOPS_URL.format(round=round_no)
        # 전역 세션 재사용
        session = get_session()
        
        def _req_html(page_url: str) -> BeautifulSoup:
            # (연결 타임아웃, 읽기 타임아웃) 튜플로 지정
            resp = session.get(page_url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")

        soup = _with_retries(lambda: _req_html(url))

        # Skip first table (navigation), process tables 2 and 3 for rank 1 and rank 2
        tables = soup.select("table.tbl_data")

        # Process 1st rank table (index 1)
        if len(tables) > 1:
            table = tables[1]
            headers = [th.get_text(strip=True) for th in table.select("thead th")]
            has_method_col = any("구분" in h for h in headers)
            rank = 1 if has_method_col else 2

            for row in table.select("tbody tr"):
                shop_data = _parse_shop_row(row, round_no, rank, has_method_col)
                if shop_data:
                    result.append(shop_data)

        # Process 2nd rank shops with pagination
        page = 1
        while True:
            if page == 1:
                # Use existing soup for first page
                current_soup = soup
            else:
                # Fetch additional pages
                page_url = f"{SHOPS_URL.format(round=round_no)}&nowPage={page}"
                try:
                    current_soup = _with_retries(lambda: _req_html(page_url))
                except Exception:
                    # If page doesn't exist, break
                    break

            # Get 2nd rank table (index 2)
            page_tables = current_soup.select("table.tbl_data")
            if len(page_tables) <= 2:
                break

            rank2_table = page_tables[2]
            rank2_rows = rank2_table.select("tbody tr")

            # If no rows found, we've reached the end
            if not rank2_rows:
                break

            # Check if this page has the same data as previous (infinite loop protection)
            first_row_cols = None
            if rank2_rows:
                first_tds = rank2_rows[0].select("td")
                if first_tds:
                    first_row_cols = [td.get_text(" ", strip=True) for td in first_tds]

            page_shops_added = 0
            for row in rank2_rows:
                shop_data = _parse_shop_row(row, round_no, 2, False)
                if shop_data:
                    # Check for duplicates (sequence numbers should be unique)
                    duplicate = any(s["sequence"] == shop_data["sequence"] and s["rank"] == 2
                                  for s in result if s.get("sequence"))
                    if not duplicate:
                        result.append(shop_data)
                        page_shops_added += 1

            # If no new shops were added, we've reached the end
            if page_shops_added == 0:
                break

            # Move to next page
            page += 1

            # Safety limit to prevent infinite loops
            if page > 20:  # Reasonable upper limit
                break

        return result
    except Exception:
        return []


def _parse_shop_row(row, round_no: int, rank: int, has_method_col: bool) -> Optional[Dict]:
    """Parse a single shop row from the table."""
    tds = row.select("td")
    if not tds:
        return None

    cols = [td.get_text(" ", strip=True) for td in tds]

    # Basic columns
    sequence = None
    try:
        sequence = int(cols[0])
    except Exception:
        pass

    name = cols[1] if len(cols) > 1 else None
    if not name:
        return None

    method = None
    address = None
    if has_method_col and len(cols) >= 5:
        # Expected: 번호, 상호명, 구분, 소재지, 위치보기
        method = cols[2] or None
        address = cols[3] or None
    else:
        # Expected: 번호, 상호명, 소재지, 위치보기
        address_text = cols[2] if len(cols) > 2 else ""
        # Attempt to extract method tokens from address text
        for token in ("반자동", "자동", "수동"):
            if token in address_text:
                method = token
                address_text = address_text.replace(token, "").strip()
                break
        address = address_text or None

    return {
        "round": round_no,
        "rank": rank,
        "sequence": sequence,
        "name": name,
        "method": method,
        "address": address,
        "winners_count": None,
    }
