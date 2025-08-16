#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
from collections import Counter
from db import get_conn

def load_stats():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT number, frequency, COALESCE(not_drawn_weeks,0), COALESCE(bonus_frequency,0)
          FROM number_frequency ORDER BY number
        """)
        rows = cur.fetchall()
        if rows:
            stats = {r['number']:{
                'frequency':r[1],
                'not_drawn_weeks':r[2],
                'bonus_frequency':r[3]
            } for r in rows}
            cur.execute("SELECT COUNT(*) FROM lotto_results")
            total = cur.fetchone()[0]
            return stats, total

        # fallback: 바로 계산
        cur.execute("SELECT num1,num2,num3,num4,num5,num6,bonus_num, draw_no FROM lotto_results")
        R = cur.fetchall()
        if not R: return {}, 0
        fr, br, last = Counter(), Counter(), {}
        for r in R:
            nums = [r['num1'],r['num2'],r['num3'],r['num4'],r['num5'],r['num6']]
            for n in nums: fr[n]+=1; last[n]=r['draw_no']
            br[r['bonus_num']]+=1
        latest = max(x['draw_no'] for x in R)
        stats = {n:{
            'frequency':fr[n],
            'bonus_frequency':br[n],
            'not_drawn_weeks': latest - last.get(n,0) if last.get(n) else latest
        } for n in range(1,46)}
        return stats, len(R)

def pick_weighted(weights, k=6):
    pool = []
    for n,w in weights.items():
        pool.extend([n]*max(1,int(w)))
    sel = set()
    while len(sel)<k and pool:
        sel.add(random.choice(pool))
    while len(sel)<k:
        sel.add(random.randint(1,45))
    return sorted(sel)

def algo_frequency(stats):
    weights = {n:max(1, s['frequency']) for n,s in stats.items()}
    return pick_weighted(weights)

def algo_overdue(stats):
    weights = {n:max(1, s['not_drawn_weeks']) for n,s in stats.items()}
    return pick_weighted(weights)

def algo_balanced(stats):
    weights = {n:max(1, 0.6*s['frequency']+0.4*s['not_drawn_weeks']) for n,s in stats.items()}
    return pick_weighted(weights)

def _latest_draw_no(cur):
    cur.execute("SELECT MAX(draw_no) FROM lotto_results")
    d = cur.fetchone()[0]
    return int(d) if d else 0

def save_reco(algoname, nums, conf=70, reason=""):
    with get_conn() as conn:
        cur = conn.cursor()
        # 테이블이 없다면 생성 (기존 스키마를 바꾸지는 않음)
        cur.execute("""
          CREATE TABLE IF NOT EXISTS recommended_numbers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numbers TEXT NOT NULL,
            algorithm TEXT,
            confidence_score INTEGER,
            reason TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        """)
        # 스키마 확인
        cols = [row['name'] for row in cur.execute("PRAGMA table_info(recommended_numbers)").fetchall()]
        has_week_no = 'week_no' in cols

        if has_week_no:
            # week_no 가 NOT NULL 인 기존 스키마 대응
            week = _latest_draw_no(cur) or 0
            if 'created_at' not in cols:
                # created_at 이 없을 수도 있으니 컬럼 집합에 맞춰 INSERT
                cur.execute("""
                  INSERT INTO recommended_numbers(numbers,algorithm,confidence_score,reason,week_no)
                  VALUES (?,?,?,?,?)
                """, (",".join(map(str,nums)), algoname, conf, reason, week))
            else:
                cur.execute("""
                  INSERT INTO recommended_numbers(numbers,algorithm,confidence_score,reason,week_no)
                  VALUES (?,?,?,?,?)
                """, (",".join(map(str,nums)), algoname, conf, reason, week))
        else:
            cur.execute("""
              INSERT INTO recommended_numbers(numbers,algorithm,confidence_score,reason)
              VALUES (?,?,?,?)
            """, (",".join(map(str,nums)), algoname, conf, reason))

def main():
    stats, total = load_stats()
    if not stats:
        print("❌ 통계가 없어 무작위 추천을 반환합니다.")
        base = sorted(random.sample(range(1,46),6))
        save_reco("random", base, 50, "데이터 부족")
        print("[random]", base)
        return

    algos = [
      ("frequency_based", lambda: algo_frequency(stats), 75, "빈출 가중"),
      ("overdue_based",   lambda: algo_overdue(stats),   70, "미출현 가중"),
      ("balanced",        lambda: algo_balanced(stats),  65, "혼합 가중")
    ]
    for name, fn, conf, why in algos:
        nums = fn()
        save_reco(name, nums, conf, why)
        print(f"[{name}] {nums} ({conf}%) - {why}")

if __name__ == "__main__":
    main()
