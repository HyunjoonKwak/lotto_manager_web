#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time, requests
from datetime import datetime
from db import get_conn

API = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="

def latest_draw_estimate():
    start = datetime(2002,12,7)
    return ((datetime.now() - start).days // 7) + 1

def fetch_draw(d):
    s = requests.Session()
    s.headers.update({'User-Agent':'Mozilla/5.0'})
    for attempt in range(3):
        try:
            r = s.get(API + str(d), timeout=10)
            if r.status_code != 200:
                time.sleep(1.2*(attempt+1)); continue
            data = r.json()
            if data.get('returnValue') != 'success':
                return None
            return {
                'draw_no': data['drwNo'],
                'draw_date': data['drwNoDate'],
                'numbers': [data[f'drwtNo{i}'] for i in range(1,7)],
                'bonus': data['bnusNo']
            }
        except Exception:
            time.sleep(1.2*(attempt+1))
    return None

def save_draw(row):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lotto_results(
              draw_no INTEGER PRIMARY KEY,
              draw_date TEXT,
              num1 INT,num2 INT,num3 INT,num4 INT,num5 INT,num6 INT,
              bonus_num INT
            )
        """)
        cur.execute("""
            INSERT OR REPLACE INTO lotto_results
            (draw_no, draw_date, num1,num2,num3,num4,num5,num6, bonus_num)
            VALUES (?,?,?,?,?,?,?,?,?)
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
    for d in range(start, latest+1):
        data = fetch_draw(d)
        if data and save_draw(data):
            ok += 1
        time.sleep(0.25)
    print(f"최근 {n}회 수집 완료: {ok}/{n}")

def backfill_missing():
    target = latest_draw_estimate()
    miss = [d for d in range(1, target+1) if not exists_draw(d)]
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
