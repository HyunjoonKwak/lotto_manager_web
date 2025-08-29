from collections import Counter, defaultdict
from itertools import combinations
from typing import List, Dict, Any, Tuple
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

def hot_numbers(draws: List[Dict[str, Any]], top_k: int = 10) -> Tuple[List[Tuple[int,int]], int | None]:
    """
    returns: ([(번호, 출현수), ...], latest_round)
    """
    if not draws:
        return ([], None)

    freq = {i: 0 for i in range(1, 46)}
    for d in draws:
        for k in ("n1","n2","n3","n4","n5","n6"):
            n = d.get(k)
            if isinstance(n, int) and 1 <= n <= 45:
                freq[n] += 1
    items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:top_k]
    latest_round = max((d.get("round") for d in draws if d.get("round")), default=None)
    return (items, latest_round)

def cold_numbers(draws: List[Dict[str, Any]], top_k: int = 10) -> Tuple[List[Tuple[int,int]], int | None]:
    """
    returns: ([(번호, 출현수), ...], latest_round) – '가장 적게 나온 번호'
    """
    if not draws:
        return ([], None)

    freq = {i: 0 for i in range(1, 46)}
    for d in draws:
        for k in ("n1","n2","n3","n4","n5","n6"):
            n = d.get(k)
            if isinstance(n, int) and 1 <= n <= 45:
                freq[n] += 1
    items = sorted(freq.items(), key=lambda x: (x[1], x[0]))[:top_k]
    latest_round = max((d.get("round") for d in draws if d.get("round")), default=None)
    return (items, latest_round)
def frequency_pairs(draws: List[Draw], top_k: int = 10):
    c = Counter()
    for d in draws:
        arr = sorted(d.numbers())
        for a,b in combinations(arr, 2):
            c[(a,b)] += 1
    items = sorted(c.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))
    return items[:top_k]
