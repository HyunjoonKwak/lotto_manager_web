import random
from typing import List, Set, Tuple, Dict
from collections import Counter, defaultdict
from ..models import Draw

NUM_MIN, NUM_MAX = 1, 45

def _freq_map(draws: List[Draw]) -> Counter:
    cnt = Counter()
    for d in draws:
        for n in d.numbers():
            cnt[n] += 1
    return cnt

def _pair_map(draws: List[Draw]) -> Dict[Tuple[int,int], int]:
    pm = defaultdict(int)
    for d in draws:
        arr = sorted(d.numbers())
        for i in range(6):
            for j in range(i+1, 6):
                a,b = arr[i], arr[j]
                pm[(a,b)] += 1
    return pm

def _weighted_pool(freq_map):
    total = sum(freq_map.values()) or 1
    pool = []
    for n in range(NUM_MIN, NUM_MAX+1):
        w = freq_map.get(n, 1)
        w = 1 + (w / total) * 200  # 빈도 기반 가중
        pool.extend([n] * int(w))
    # 저빈도 숫자에도 기회 부여(콜드숫자 보정)
    for n in range(NUM_MIN, NUM_MAX+1):
        if freq_map.get(n,0) <= 2:
            pool.extend([n]*5)
    return pool

def _validate_combo(nums: Set[int]) -> bool:
    if len(nums) != 6:
        return False
    arr = sorted(nums)
    consec = sum(1 for i in range(1,6) if arr[i] == arr[i-1]+1)
    if consec > 2:
        return False
    odd = sum(1 for x in arr if x % 2 == 1)
    if odd in (0,1,5,6):
        return False
    return True

def _reason_for_combo(combo: List[int], freq: Counter, pair_map: Dict[Tuple[int,int],int]) -> str:
    arr = sorted(combo)
    top3 = sorted(arr, key=lambda n: (-freq.get(n,0), n))[:3]
    pair_hits = []
    for i in range(6):
        for j in range(i+1,6):
            a,b = arr[i],arr[j]
            pair_hits.append(pair_map.get((a,b)) or pair_map.get((b,a), 0))
    pair_hits.sort(reverse=True)
    pair_top = pair_hits[:2] if pair_hits else []
    even = sum(1 for x in arr if x%2==0)
    odd = 6-even
    parts = []
    if top3:
        parts.append(f"상대적 빈출 {', '.join(map(str,top3))}")
    if pair_top and sum(pair_top) > 0:
        parts.append(f"페어 시너지(상위): {sum(pair_top)}")
    parts.append(f"홀짝밸런스 {odd}:{even}")
    return " / ".join(parts)

def recommend_full_with_reasons(draws: List[Draw], k: int = 5):
    freq = _freq_map(draws)
    pair_map = _pair_map(draws)
    pool = _weighted_pool(freq)
    results = []
    seen = set()
    tries = 0
    while len(results) < k and tries < 20000:
        cand = set(random.sample(pool, 6))
        key = tuple(sorted(cand))
        if key in seen:
            tries += 1; continue
        if _validate_combo(cand):
            combo = list(sorted(cand))
            reason = _reason_for_combo(combo, freq, pair_map)
            results.append((combo, reason))
            seen.add(key)
        tries += 1
    while len(results) < k:
        combo = sorted(random.sample(range(NUM_MIN, NUM_MAX+1), 6))
        results.append((combo, "기본 난수 보정"))
    return results

def recommend_semi(draws: List[Draw], k: int = 5) -> List[List[int]]:
    # 3-number for semi-auto
    freq = _freq_map(draws)
    pool = _weighted_pool(freq)
    results = []
    seen = set()
    tries = 0
    while len(results) < k and tries < 10000:
        cand = set(random.sample(pool, 3))
        key = tuple(sorted(cand))
        if key in seen:
            tries += 1; continue
        arr = sorted(cand)
        odd = sum(1 for x in arr if x % 2 == 1)
        if odd in (0,3):
            tries += 1; continue
        results.append(arr)
        seen.add(key)
        tries += 1
    while len(results) < k:
        results.append(sorted(random.sample(range(NUM_MIN, NUM_MAX+1), 3)))
    return results
