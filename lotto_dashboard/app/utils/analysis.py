from collections import Counter, defaultdict
from itertools import combinations
from typing import List, Tuple, Dict
from ..models import Draw

def get_all_numbers(draws: List[Draw]) -> List[int]:
    nums = []
    for d in draws:
        nums.extend(d.numbers())
    return nums

def frequency_single(draws: List[Draw]) -> List[Tuple[int,int]]:
    c = Counter(get_all_numbers(draws))
    return sorted(c.items(), key=lambda x: (-x[1], x[0]))

def last_seen_round(draws: List[Draw]) -> Dict[int, int]:
    """각 번호가 마지막으로 등장한 회차(없으면 0)."""
    last = {n: 0 for n in range(1,46)}
    for d in draws:
        r = d.round
        for n in d.numbers():
            last[n] = max(last[n], r)
    return last

def cold_numbers(draws: List[Draw], top_k: int = 10):
    """최근에 안 나온 숫자 TopK. (최근 회차 - 마지막 출현 회차) 큰 순."""
    if not draws:
        return []
    latest = max(d.round for d in draws)
    last = last_seen_round(draws)
    # (번호, 마지막출현회차, 경과회차)
    rows = [(n, last[n], latest - last[n] if last[n] else latest) for n in range(1,46)]
    rows.sort(key=lambda x: (-x[2], x[0]))  # 가장 오래 안 나온 순
    return rows[:top_k], latest

def frequency_pairs(draws: List[Draw], top_k: int = 10):
    c = Counter()
    for d in draws:
        arr = sorted(d.numbers())
        for a,b in combinations(arr, 2):
            c[(a,b)] += 1
    items = sorted(c.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
    return items[:top_k]
