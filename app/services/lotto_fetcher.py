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
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Cache-Control": "max-age=0",
    "Referer": "https://www.dhlottery.co.kr/"
}
# 연결 타임아웃과 읽기 타임아웃을 분리 (더 넉넉하게 설정)
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 60

# 요청 간격 설정 (서버 부하 방지)
REQUEST_DELAY = 1.5  # 요청 간 1.5초 대기

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

    # urllib3 레벨에서 재시도 전략 설정 (더 강화)
    retry_strategy = Retry(
        total=5,  # 최대 5회 재시도
        backoff_factor=2,  # 백오프 팩터 증가
        status_forcelist=[429, 500, 502, 503, 504, 522, 524],  # 더 많은 상태 코드 포함
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=False  # 상태 오류 시 즉시 예외 발생하지 않음
    )

    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # 쿠키 지원 활성화 (브라우저처럼 동작)
    session.cookies.set_policy(None)

    # cookies.txt 파일이 있으면 로드
    import os
    cookies_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cookies.txt')
    if os.path.exists(cookies_file):
        try:
            from http.cookiejar import MozillaCookieJar
            jar = MozillaCookieJar(cookies_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies = jar
            print(f"쿠키 파일 로드됨: {len(jar)} 개 쿠키")
        except Exception as e:
            print(f"쿠키 파일 로드 실패: {e}")

    return session


# 마지막 요청 시간 추적 (전역)
_last_request_time = 0.0

def _rate_limit():
    """요청 간격 제한 (서버 부하 방지)"""
    global _last_request_time
    current_time = time.time()
    elapsed = current_time - _last_request_time

    if elapsed < REQUEST_DELAY:
        sleep_time = REQUEST_DELAY - elapsed
        print(f"요청 간격 제한: {sleep_time:.1f}초 대기")
        time.sleep(sleep_time)

    _last_request_time = time.time()

def _with_retries(fn: Callable[[], T], retries: int = 5, delay: float = 3.0) -> T:
    """재시도 로직 - 지수 백오프와 지연 시간 포함"""
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            # 요청 간격 제한 적용
            _rate_limit()
            result = fn()
            if attempt > 0:  # 재시도가 있었던 경우
                print(f"재시도 {attempt + 1}회차에서 성공")
            return result
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError, socket.timeout) as exc:
            last_exc = exc
            if attempt < retries - 1:  # 마지막 시도가 아닌 경우만 대기
                wait_time = delay * (2 ** attempt)  # 지수 백오프
                print(f"네트워크 오류로 재시도 {attempt + 1}/{retries}, {wait_time:.1f}초 후 재시도: {type(exc).__name__}: {str(exc)}")
                time.sleep(wait_time)
            else:
                print(f"모든 재시도 실패: {type(exc).__name__}: {str(exc)}")
        except requests.exceptions.RequestException as exc:  # 기타 요청 관련 오류
            last_exc = exc
            if attempt < retries - 1:
                wait_time = delay * (2 ** attempt)
                print(f"요청 오류로 재시도 {attempt + 1}/{retries}, {wait_time:.1f}초 후 재시도: {type(exc).__name__}: {str(exc)}")
                time.sleep(wait_time)
            else:
                print(f"모든 재시도 실패 (요청 오류): {type(exc).__name__}: {str(exc)}")
        except Exception as exc:  # 기타 오류
            last_exc = exc
            print(f"예상치 못한 오류 발생: {type(exc).__name__}: {str(exc)}")
            break  # 네트워크 오류가 아닌 경우 즉시 중단

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

    # 당첨금액 및 당첨자수 정보 추출 (API에서 제공하는 경우)
    result = {
        "round": round_no,
        "draw_date": draw_date,
        "numbers": numbers,
        "bonus": bonus,
    }

    # 추가 정보가 있는 경우 포함
    if "totSellamnt" in data:  # 총 판매액
        result["total_sales"] = data["totSellamnt"]

    # 1등 정보
    if "firstWinamnt" in data:  # 1등 당첨금액
        result["first_prize_amount"] = data["firstWinamnt"]
    if "firstPrzwnerCo" in data:  # 1등 당첨자수
        result["first_prize_winners"] = data["firstPrzwnerCo"]

    # 2등 정보 (보너스 번호 맞춘 경우)
    if "scndWinamnt" in data:  # 2등 당첨금액
        result["second_prize_amount"] = data["scndWinamnt"]
    if "scndPrzwnerCo" in data:  # 2등 당첨자수
        result["second_prize_winners"] = data["scndPrzwnerCo"]

    # 3등 정보 (5개 번호 맞춘 경우)
    if "thrdWinamnt" in data:  # 3등 당첨금액
        result["third_prize_amount"] = data["thrdWinamnt"]
    if "thrdPrzwnerCo" in data:  # 3등 당첨자수
        result["third_prize_winners"] = data["thrdPrzwnerCo"]

    # 4등 정보 (4개 번호 맞춘 경우)
    if "frthWinamnt" in data:  # 4등 당첨금액 (보통 50,000원 고정)
        result["fourth_prize_amount"] = data["frthWinamnt"]
    if "frthPrzwnerCo" in data:  # 4등 당첨자수
        result["fourth_prize_winners"] = data["frthPrzwnerCo"]

    # 5등 정보 (3개 번호 맞춘 경우)
    if "fifthWinamnt" in data:  # 5등 당첨금액 (보통 5,000원 고정)
        result["fifth_prize_amount"] = data["fifthWinamnt"]
    if "fifthPrzwnerCo" in data:  # 5등 당첨자수
        result["fifth_prize_winners"] = data["fifthPrzwnerCo"]

    return result


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
                # Fetch additional pages with extra delay for pagination
                page_url = f"{SHOPS_URL.format(round=round_no)}&nowPage={page}"
                try:
                    # Add extra delay for pagination requests to reduce server load
                    if page > 1:
                        print(f"페이지네이션 {page}페이지 요청 전 추가 대기")
                        time.sleep(REQUEST_DELAY)  # Extra delay for pagination
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
