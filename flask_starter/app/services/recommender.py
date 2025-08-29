from __future__ import annotations

import random
from collections import Counter
from typing import Iterable


def auto_recommend(draw_numbers: Iterable[list[int]], count: int = 3) -> list[list[int]]:
    """Generate 'count' automatic recommendations based on historical frequency.
    Simple heuristic: weighted sampling by number frequency, ensure sorted unique set of 6.
    """
    freq = Counter(n for seq in draw_numbers for n in seq)
    pool = list(range(1, 46))
    weights = [freq.get(n, 1) for n in pool]
    recs: list[list[int]] = []
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


def semi_auto_recommend(fixed_numbers: Iterable[int] | None, count: int = 2) -> list[list[int]]:
    """Generate 'count' semi-auto recommendations given user-fixed numbers (0-5 numbers)."""
    fixed_set = set(fixed_numbers or [])
    pool = [n for n in range(1, 46) if n not in fixed_set]
    recs: list[list[int]] = []
    for _ in range(count):
        remain = 6 - len(fixed_set)
        picks = sorted(fixed_set | set(random.sample(pool, remain)))
        recs.append(picks)
    return recs
