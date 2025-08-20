#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import Counter
from db import get_conn

def recompute_number_frequency():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT draw_no,num1,num2,num3,num4,num5,num6,bonus_num
          FROM lotto_results ORDER BY draw_no
        """)
        rows = cur.fetchall()

    if not rows:
        print("❌ 분석할 데이터가 없습니다."); return

    freq = Counter()
    bonus = Counter()
    last  = {}

    for r in rows:
        draw = r["draw_no"]
        nums = [r["num1"], r["num2"], r["num3"], r["num4"], r["num5"], r["num6"]]
        for n in nums:
            freq[n] += 1
            last[n] = draw
        bonus[r["bonus_num"]] += 1

    latest = rows[-1]["draw_no"]

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          CREATE TABLE IF NOT EXISTS number_frequency(
            number INTEGER PRIMARY KEY,
            frequency INT DEFAULT 0,
            bonus_frequency INT DEFAULT 0,
            last_drawn INT DEFAULT 0,
            not_drawn_weeks INT DEFAULT 0
          )
        """)
        for n in range(1,46):
            cur.execute("""
              INSERT INTO number_frequency(number, frequency, bonus_frequency, last_drawn, not_drawn_weeks)
              VALUES (?,?,?,?,?)
              ON CONFLICT(number) DO UPDATE SET
                frequency=excluded.frequency,
                bonus_frequency=excluded.bonus_frequency,
                last_drawn=excluded.last_drawn,
                not_drawn_weeks=excluded.not_drawn_weeks
            """, (n, freq[n], bonus[n], last.get(n,0), (latest - last.get(n,0)) if last.get(n) else latest))

    print("📊 number_frequency 갱신 완료")

def main():
    recompute_number_frequency()

if __name__ == "__main__":
    main()
