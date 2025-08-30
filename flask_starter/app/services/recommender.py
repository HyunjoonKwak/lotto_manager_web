import random
from collections import Counter
from typing import Iterable, List, Optional


def auto_recommend(draw_numbers: Iterable[List[int]], count: int = 3) -> List[List[int]]:
    """Generate 'count' automatic recommendations based on historical frequency.
    Simple heuristic: weighted sampling by number frequency, ensure sorted unique set of 6.
    """
    freq = Counter(n for seq in draw_numbers for n in seq)
    pool = list(range(1, 46))
    weights = [freq.get(n, 1) for n in pool]
    recs: List[List[int]] = []
    for _ in range(count):
        picks: set[int] = set()
        # weighted choice without replacement
        candidates = pool.copy()
        w = weights.copy()
        for _ in range(6):
            n = random.choices(candidates, weights=w, k=1)[0]
            idx = candidates.index(n)
            candidates.pop(idx)
            w.pop(idx)
            picks.add(n)
        recs.append(sorted(picks))
    return recs


def semi_auto_recommend(fixed_numbers: Optional[Iterable[int]], count: int = 2) -> List[List[int]]:
    """Generate 'count' semi-auto recommendations given user-fixed numbers (0-5 numbers)."""
    fixed_set = set(fixed_numbers or [])
    pool = [n for n in range(1, 46) if n not in fixed_set]
    recs: List[List[int]] = []
    for _ in range(count):
        remain = 6 - len(fixed_set)
        picks = sorted(fixed_set | set(random.sample(pool, remain)))
        recs.append(picks)
    return recs
