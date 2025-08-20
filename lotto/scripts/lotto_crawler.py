#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time, requests
from datetime import datetime
from db import get_conn

API = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="

def latest_draw_estimate():
    # 2002-12-07 (1회차 기준 토요일)부터 매주 1씩 증가
    start = datetime(2002, 12, 7)
    return ((datetime.now() - start).days // 7) + 1

def fetch_draw(d):
    s = requests.Session()
    s.headers.update({'User-Agent':'Mozilla/5.0'})
    for attempt in range(3):
        try:
            r = s.get(API + str(d), timeout=8)
            if r.ok:
                data = r.json()
                if data.get("returnValue") == "success":
                    return {
                        'draw_no'  : int(data['drwNo']),
                        'draw_date': data['drwNoDate'],
                        'numbers'  : [int(data[f'drwtNo{i}']) for i in range(1,7)],
                        'bonus'    : int(data['bnusNo']),
                    }
        except Exception:
            time.sleep(0.8 * (attempt + 1))
    return None

def save_draw(row):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          CREATE TABLE IF NOT EXISTS lotto_results(
            draw_no    INTEGER PRIMARY KEY,
            draw_date  TEXT,
            num1 INT, num2 INT, num3 INT, num4 INT, num5 INT, num6 INT,
            bonus_num  INT
          )
        """)
        cur.execute("""
          INSERT INTO lotto_results(draw_no, draw_date, num1, num2, num3, num4, num5, num6, bonus_num)
          VALUES (?,?,?,?,?,?,?,?,?)
          ON CONFLICT(draw_no) DO UPDATE SET
            draw_date=excluded.draw_date,
            num1=excluded.num1, num2=excluded.num2, num3=excluded.num3,
            num4=excluded.num4, num5=excluded.num5, num6=excluded.num6,
            bonus_num=excluded.bonus_num
        """, (row['draw_no'], row['draw_date'], *row['numbers'], row['bonus']))
    return True

def exists_draw(d):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM lotto_results WHERE draw_no=?", (d,))
        return cur.fetchone() is not None

def collect_recent(n=50):
    latest = latest_draw_estimate()
    start = max(1, latest - n + 1)
    ok = 0
    for d in range(start, latest + 1):
        if exists_draw(d):
            continue
        data = fetch_draw(d)
        if data and save_draw(data):
            ok += 1
        time.sleep(0.25)
    print(f"최근 {n}회 수집 완료: {ok}/{n}")

def backfill_missing():
    target = latest_draw_estimate()
    miss = [d for d in range(1, target + 1) if not exists_draw(d)]
    print("누락 회차:", len(miss))
    for d in miss[:200]:  # 과도한 호출 방지
        data = fetch_draw(d)
        if data:
            save_draw(data)
        time.sleep(0.25)

def main():
    collect_recent(50)
    backfill_missing()

if __name__ == "__main__":
    main()
