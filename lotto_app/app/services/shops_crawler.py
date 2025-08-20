import os, time, hashlib
import requests
from bs4 import BeautifulSoup
from flask import current_app
from app.models import db, Shop

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"

def _raw_dir():
    d = current_app.config.get("RAW_CACHE_DIR", "/tmp/lotto_raw")
    os.makedirs(d, exist_ok=True)
    return d

def _save_raw(name: str, content: bytes):
    path = os.path.join(_raw_dir(), name)
    with open(path, "wb") as f:
        f.write(content)
    return path

def _hash_row(round_no, rank, name, address):
    s = f"{round_no}||{rank}||{name}||{address}"
    return hashlib.sha256(s.encode()).hexdigest()

def _upsert(rows):
    made = 0
    for r in rows:
        raw_hash = r["raw_hash"]
        exists = db.session.execute(
            db.text("SELECT id FROM shops WHERE raw_hash = :h LIMIT 1"),
            {"h": raw_hash}
        ).first()
        if exists:
            continue
        shop = Shop(
            round=r["round"],
            rank=r.get("rank", 1),
            name=r.get("name"),
            address=r.get("address"),
            lat=r.get("lat"),
            lon=r.get("lon"),
            raw_hash=raw_hash,
        )
        db.session.add(shop)
        made += 1
    if made:
        db.session.commit()
    return made

def _smart_decode(content: bytes) -> str:
    # dhlottery는 EUC-KR(meta로 EUC-KR 선언)인 경우가 많다.
    # 깨짐 방지를 위해 cp949로 우선 시도, 실패 시 fallback
    try:
        return content.decode("cp949", errors="ignore")
    except Exception:
        return content.decode("utf-8", errors="ignore")

def _parse_table_like(soup: BeautifulSoup, round_no: int):
    cand_tables = []
    cand_tables += soup.select("table.tbl_data")
    cand_tables += soup.select("table.tbl_data_col")
    if not cand_tables:
        # article 내부 첫 번째 테이블 시도
        art = soup.select_one("article") or soup
        cand_tables = art.select("table")

    rows = []
    for table in cand_tables:
        # 헤더 추출
        headers = [th.get_text(strip=True) for th in table.select("thead th")]
        if not headers:
            first_tr = table.select_one("tr")
            if first_tr:
                headers = [td.get_text(strip=True) for td in first_tr.select("th,td")]

        # 헤더 인덱스 매핑
        def find_idx(keys):
            for k in keys:
                if k and headers:
                    for h in headers:
                        if k in h:
                            return headers.index(h)
            return None

        idx_name = find_idx(["상호", "상호명", "판매점", "점포명"])
        idx_addr = find_idx(["소재지", "주소", "위치", "지번주소", "도로명주소"])
        idx_rank = find_idx(["번호", "순번", "등수", "순위"])

        body_trs = table.select("tbody tr")
        if not body_trs:
            trs = table.select("tr")
            body_trs = trs[1:] if len(trs) > 1 else []

        got = 0
        for tr in body_trs:
            cols = [td.get_text(" ", strip=True) for td in tr.select("td")]
            if not cols:
                continue
            name = cols[idx_name] if (idx_name is not None and idx_name < len(cols)) else ""
            addr = cols[idx_addr] if (idx_addr is not None and idx_addr < len(cols)) else ""
            if not name and not addr:
                # 일부 표는 "가맹점명 | 소재지 | 판매구분" 식으로 되어 있음
                # 최소 2개 컬럼 이상일 때 휴리스틱으로 뽑기
                if len(cols) >= 2:
                    name = name or cols[0]
                    addr = addr or cols[1]
                else:
                    continue

            rank = 1
            if idx_rank is not None and idx_rank < len(cols):
                txt = cols[idx_rank]
                num = "".join(ch for ch in txt if ch.isdigit())
                try:
                    if num:
                        rank = int(num)
                except Exception:
                    pass

            rows.append({
                "round": round_no,
                "rank": rank,
                "name": name,
                "address": addr,
                "lat": None, "lon": None,
                "raw_hash": _hash_row(round_no, rank, name, addr),
            })
            got += 1

        if got:
            return rows
    return rows

def _parse_list_like(soup: BeautifulSoup, round_no: int):
    rows = []
    # 모바일/대체 리스트 패턴들
    for li in soup.select("ul li"):
        name_el = (li.select_one("strong.store_name") or
                   li.select_one("strong") or
                   li.select_one(".name") or
                   li.select_one(".store") or
                   li.select_one(".tit"))
        addr_el = (li.select_one("span.store_addr") or
                   li.select_one("span.addr") or
                   li.select_one(".address") or
                   li.select_one(".desc") or
                   li.select_one(".txt"))
        if not name_el and not addr_el:
            continue
        name = name_el.get_text(strip=True) if name_el else ""
        addr = addr_el.get_text(strip=True) if addr_el else ""
        if not name and not addr:
            continue
        rows.append({
            "round": round_no,
            "rank": 1,
            "name": name,
            "address": addr,
            "lat": None, "lon": None,
            "raw_hash": _hash_row(round_no, 1, name, addr),
        })
    return rows

def fetch_shops_for_round(round_no: int):
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645",
        "Connection": "keep-alive",
    })

    # 후보 URL들을 순차 시도 (회차별 1등 판매점 페이지들)
    candidates = [
        f"https://www.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={round_no}",
        f"https://m.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645&drwNo={round_no}",
        # 일부 환경에서 rank/gameNo 조합이 필요한 경우가 있어 예비로 시도
        f"https://www.dhlottery.co.kr/store.do?method=topStore&rank=1&pageGubun=L645&drwNo={round_no}",
        f"https://www.dhlottery.co.kr/store.do?method=topStore&gameNo=5133&pageGubun=L645&drwNo={round_no}",
    ]

    last_html_path = None
    for idx, url in enumerate(candidates, 1):
        r = s.get(url, timeout=15)
        if r.status_code != 200:
            continue
        html = _smart_decode(r.content)
        # Raw 저장 (디버깅)
        last_html_path = _save_raw(f"shops_r{round_no}_cand{idx}.html", r.content)
        soup = BeautifulSoup(html, "lxml")

        # 먼저 테이블 기반 파싱
        rows = _parse_table_like(soup, round_no)
        if rows:
            print(f"[shops] parsed {len(rows)} rows from cand{idx}: {url} -> {last_html_path}")
            return rows

        # 리스트 기반 파싱 시도
        rows = _parse_list_like(soup, round_no)
        if rows:
            print(f"[shops] parsed {len(rows)} rows (list) from cand{idx}: {url} -> {last_html_path}")
            return rows

    # 최후 보조(회차별 아님) — 최신 상위 점포 리스트라도 가져오기
    u3 = "https://www.dhlottery.co.kr/store.do?method=topStore&pageGubun=L645"
    r3 = s.get(u3, timeout=15)
    if r3.status_code == 200:
        html3 = _smart_decode(r3.content)
        p3 = _save_raw(f"topstore_latest_{int(time.time())}.html", r3.content)
        soup3 = BeautifulSoup(html3, "lxml")
        rows3 = _parse_table_like(soup3, round_no)
        if not rows3:
            rows3 = _parse_list_like(soup3, round_no)
        if rows3:
            print(f"[shops] fallback(list) {len(rows3)} rows from latest: {u3} -> {p3}")
            return rows3

    print(f"[shops] no rows parsed for round={round_no}. last_html={last_html_path}")
    return []

def update_shops_round(round_no: int):
    rows = fetch_shops_for_round(round_no)
    added = _upsert(rows)
    return {"round": round_no, "found": len(rows), "inserted": added}
