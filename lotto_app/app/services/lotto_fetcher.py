import requests
import time
from datetime import datetime
from flask import current_app
from app.models import db, Draw

BASE = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round}"

def fetch_round(round_no: int):
    url = BASE.format(round=round_no)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("returnValue") != "success":
        return None
    draw_date = datetime.strptime(data["drwNoDate"], "%Y-%m-%d").date()
    nums = [data[f"drwtNo{i}"] for i in range(1, 7)]
    return {
        "round": int(data["drwNo"]),
        "draw_date": draw_date,
        "numbers": nums,
        "bonus": int(data["bnusNo"]),
    }

def upsert_draw(d):
    obj = Draw.query.get(d["round"])
    if obj is None:
        obj = Draw(
            round=d["round"],
            draw_date=d["draw_date"],
            n1=d["numbers"][0],
            n2=d["numbers"][1],
            n3=d["numbers"][2],
            n4=d["numbers"][3],
            n5=d["numbers"][4],
            n6=d["numbers"][5],
            bonus=d["bonus"],
        )
        db.session.add(obj)
    else:
        # 업데이트(변경 있을 때)
        obj.draw_date = d["draw_date"]
        obj.n1, obj.n2, obj.n3, obj.n4, obj.n5, obj.n6 = d["numbers"]
        obj.bonus = d["bonus"]
    db.session.commit()
    return obj

def fetch_until_gap(start_round=1, sleep=0.2):
    """
    start_round부터 성공하는 동안 계속 가져오다가
    실패(미발표 회차) 나오면 중단
    """
    cur = start_round
    last = None
    while True:
        data = fetch_round(cur)
        if not data:
            break
        last = upsert_draw(data)
        cur += 1
        if sleep:
            time.sleep(sleep)
    return last  # 마지막 성공 회차

def fetch_latest_known(sleep=0.0):
    """
    DB에 있는 최대 회차 다음부터 시도하여 최신 발표분까지 반영.
    """
    max_row = db.session.execute(db.text("SELECT MAX(round) FROM draws")).scalar()
    start = (max_row or 0) + 1
    if start <= 0:
        start = 1
    return fetch_until_gap(start_round=start, sleep=sleep)
