#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random, sys
from typing import Dict, List, Tuple
from db import get_conn

def ensure_tables():
    with get_conn() as conn:
        conn.execute("""
          CREATE TABLE IF NOT EXISTS recommended_numbers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numbers TEXT NOT NULL,
            algorithm TEXT,
            confidence_score INTEGER,
            reason TEXT,
            week_no INTEGER,
            slot INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        """)
        conn.execute("""
          CREATE UNIQUE INDEX IF NOT EXISTS ux_reco_week_algo_slot
          ON recommended_numbers(week_no, algorithm, slot)
        """)
        conn.execute("""
          CREATE TABLE IF NOT EXISTS recommendation_results(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rec_id INTEGER NOT NULL,
            draw_no INTEGER NOT NULL,
            matched_count INTEGER NOT NULL,
            bonus_matched INTEGER NOT NULL,
            rank TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
          )
        """)
        conn.execute("""
          CREATE UNIQUE INDEX IF NOT EXISTS ux_results_rec_draw
          ON recommendation_results(rec_id, draw_no)
        """)

def load_stats():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT number, COALESCE(frequency,0), COALESCE(not_drawn_weeks,0)
          FROM number_frequency ORDER BY number
        """)
        rows = cur.fetchall()
        stats = {r['number']: {'frequency': int(r[1]), 'not_drawn_weeks': int(r[2])} for r in rows} if rows else {}
        cur.execute("SELECT MAX(draw_no) FROM lotto_results")
        latest = int(cur.fetchone()[0] or 0)
    return stats, latest

def pick_weighted(weights: Dict[int, float], k: int) -> List[int]:
    pool = list(weights.items())
    chosen: List[int] = []
    for _ in range(k):
        if not pool: break
        total = sum(max(0.0,w) for _,w in pool)
        if total <= 0:
            n = random.choice([n for n,_ in pool])
            chosen.append(n); pool = [(nn,ww) for nn,ww in pool if nn!=n]; continue
        r = random.uniform(0,total); acc = 0.0
        for i,(n,w) in enumerate(pool):
            acc += max(0.0,w)
            if r <= acc:
                chosen.append(n); pool.pop(i); break
    while len(chosen) < k:
        n = random.randint(1,45)
        if n not in chosen: chosen.append(n)
    return sorted(chosen)

def algo_auto6(stats: Dict[int,dict]) -> List[int]:
    if not stats: return sorted(random.sample(range(1,46),6))
    weights = {n: max(1.0, 0.6*s['frequency'] + 0.4*s['not_drawn_weeks']) for n,s in stats.items()}
    return pick_weighted(weights, 6)

def algo_semi_auto_digit3(stats: Dict[int,dict], k: int = 3) -> List[int]:
    pool = [n for n in range(1,46) if '3' in str(n)]
    if len(pool) < k: pool = list(range(1,46))
    if stats:
        weights = {n: max(1.0, float(stats.get(n,{}).get('frequency',1))) for n in pool}
        return pick_weighted(weights, k)
    return sorted(random.sample(pool, k))

def upsert_reco(week_no: int, algorithm: str, slot: int, nums: List[int], conf: int, reason: str):
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
              INSERT INTO recommended_numbers(numbers,algorithm,confidence_score,reason,week_no,slot)
              VALUES (?,?,?,?,?,?)
            """, (",".join(map(str,nums)), algorithm, conf, reason, week_no, slot))
            return cur.lastrowid, True
        except Exception:
            cur.execute("SELECT id FROM recommended_numbers WHERE week_no=? AND algorithm=? AND slot=?",
                        (week_no, algorithm, slot))
            row = cur.fetchone()
            return (row[0] if row else None), False

def generate_for_week(week_no: int, per_algo: int = 5) -> List[Tuple[str,int,List[int],bool]]:
    ensure_tables()
    stats, _ = load_stats()
    out = []
    for slot in range(1, per_algo+1):
        a = algo_auto6(stats)
        rid, ins = upsert_reco(week_no, "auto6", slot, a, 75, f"통계기반 가중랜덤 6개 (#{slot})")
        out.append(("auto6", slot, a, ins))
        b = algo_semi_auto_digit3(stats)
        rid, ins = upsert_reco(week_no, "semi_auto_digit3", slot, b, 60, f"'3' 포함 번호 3개(반자동 #{slot})")
        out.append(("semi_auto_digit3", slot, b, ins))
    return out

def validate_week(draw_no: int):
    ensure_tables()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT num1,num2,num3,num4,num5,num6,bonus_num FROM lotto_results WHERE draw_no=?", (draw_no,))
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "해당 회차 당첨결과가 DB에 없음"}
        win = set(int(x) for x in row[:6]); bonus = int(row[6])
        cur.execute("SELECT id,numbers,algorithm FROM recommended_numbers WHERE week_no=?", (draw_no,))
        recs = cur.fetchall()
        results = []
        for rid,numbers,algo in recs:
            arr = [int(x) for x in numbers.split(",") if x.strip()]
            s = set(arr); matched = len(win & s); bonus_hit = int(bonus in s)
            if len(arr) == 6:
                rank = "1등" if matched==6 else ("2등" if matched==5 and bonus_hit else
                        "3등" if matched==5 else "4등" if matched==4 else
                        "5등" if matched==3 else "미당첨")
            else:
                rank = "N/A(반자동 추천 3개)"
            conn.execute("""
              INSERT OR IGNORE INTO recommendation_results(rec_id,draw_no,matched_count,bonus_matched,rank)
              VALUES (?,?,?,?,?)
            """, (rid, draw_no, matched, bonus_hit, rank))
            results.append({"rec_id": rid, "algorithm": algo, "numbers": arr,
                            "matched": matched, "bonus": bonus_hit, "rank": rank})
    return {"success": True, "draw_no": draw_no, "results": results}

def main():
    _, latest = load_stats()
    week_no = latest + 1
    args = sys.argv[1:]
    if args:
        if args[0] == "--next": week_no = latest + 1; args = args[1:]
        elif args[0].isdigit(): week_no = int(args[0]); args = args[1:]
    if args and args[0] == "--validate":
        print(validate_week(week_no)); return
    res = generate_for_week(week_no, per_algo=5)
    for name,slot,nums,ins in res:
        tag = "CREATED" if ins else "CACHED"
        print(f"[{tag}] week={week_no} {name}[#{slot}]: {nums}")

if __name__ == "__main__":
    main()
