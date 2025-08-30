from datetime import datetime
from typing import Iterable, Callable, TypeVar, Optional, List, Dict

import requests
from bs4 import BeautifulSoup

NUMBERS_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round}"
SHOPS_URL = "https://www.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={round}"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
DEFAULT_TIMEOUT = 12

T = TypeVar("T")


def _with_retries(fn: Callable[[], T], retries: int = 3) -> T:
    last_exc: Optional[Exception] = None
    for _ in range(retries):
        try:
            return fn()
        except Exception as exc:  # network or parse errors
            last_exc = exc
    assert last_exc is not None
    raise last_exc


def fetch_draw(round_no: int) -> Dict:
    """Fetch lotto draw info by round. Replace URL/parsing with real source later."""
    # Example placeholder using official API-like JSON endpoint if available.
    # Here we structure a mock example for wiring. Replace with actual endpoint.
    url = NUMBERS_URL.format(round=round_no)
    def _req() -> Dict:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS)
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
        def _req_html(page_url: str) -> BeautifulSoup:
            resp = requests.get(page_url, timeout=DEFAULT_TIMEOUT, headers=DEFAULT_HEADERS)
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
