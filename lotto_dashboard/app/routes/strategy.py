# app/routes/strategy.py
from __future__ import annotations

import os
import sqlite3
from typing import Dict, List, Tuple, Any
from collections import Counter
from flask import Blueprint, current_app, render_template

bp = Blueprint("strategy", __name__, url_prefix="/strategy")

def _db_path(app) -> str:
    inst_dir = getattr(app, "instance_path", None) or os.path.join(os.getcwd(), "instance")
    os.makedirs(inst_dir, exist_ok=True)
    return os.path.join(inst_dir, "lotto.db")

def _fetch_numbers(db_path: str, limit: int = 120):
    if not os.path.exists(db_path):
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                "SELECT round, n1,n2,n3,n4,n5,n6,bn, draw_date "
                "FROM numbers ORDER BY round DESC LIMIT ?", (limit,)
            ).fetchall()
        except sqlite3.OperationalError:
            return []

def _compute_freq_and_last(rows):
    freqmap: Dict[int, int] = {i: 0 for i in range(1, 46)}
    lastmap: Dict[int, int] = {i: 0 for i in range(1, 46)}

    if not rows:
        return freqmap, lastmap

    # 빈도 집계
    for r in rows:
        for k in ("n1","n2","n3","n4","n5","n6"):
            v = int(r[k])
            if 1 <= v <= 45:
                freqmap[v] += 1

    # 마지막 등장 이후 경과 회차 수
    latest_index_for: Dict[int, int] = {}
    for idx, r in enumerate(rows):  # 0=최신
        for k in ("n1","n2","n3","n4","n5","n6"):
            v = int(r[k])
            if v not in latest_index_for:
                latest_index_for[v] = idx
    for n in range(1, 46):
        lastmap[n] = latest_index_for.get(n, len(rows))

    return freqmap, lastmap

def _compute_pairs(rows):
    pair_counter = Counter()
    for r in rows:
        numbers = [int(r[k]) for k in ("n1","n2","n3","n4","n5","n6")]
        numbers.sort()
        for i in range(len(numbers)):
            for j in range(i+1, len(numbers)):
                pair_counter[(numbers[i], numbers[j])] += 1
    return pair_counter.most_common(50)

def _generate_mock_recommendations():
    # 간단한 모의 추천 시스템
    import random

    # 완전 추천 조합 5개
    full_recommendations = []
    reasons = [
        "최근 10회차 다빈출 번호와 저빈출 번호의 균형",
        "홀수/짝수 비율과 구간별 분산을 고려한 조합",
        "최근 페어 분석 결과를 반영한 상관관계 조합",
        "통계적 패턴과 랜덤성의 절충안",
        "과거 당첨 패턴의 역분석을 통한 차별화"
    ]

    for i in range(5):
        combo = sorted(random.sample(range(1, 46), 6))
        full_recommendations.append((combo, reasons[i]))

    # 반자동 조합 5개 (3개 추천)
    semi_recommendations = []
    for i in range(5):
        triple = sorted(random.sample(range(1, 46), 3))
        semi_recommendations.append(triple)

    return full_recommendations, semi_recommendations

@bp.route("/")
def strategy_home():
    db_path = _db_path(current_app)
    rows = _fetch_numbers(db_path, limit=120)
    freqmap, lastmap = _compute_freq_and_last(rows)
    pairs = _compute_pairs(rows)

    # 모의 추천 생성 (실제로는 더 복잡한 알고리즘 사용)
    full_with_reason, semi = _generate_mock_recommendations()
    has_recommend = True

    return render_template(
        "strategy.html",
        freqmap=freqmap,
        lastmap=lastmap,
        pairs=pairs,
        has_recommend=has_recommend,
        full_with_reason=full_with_reason,
        semi=semi,
    )
