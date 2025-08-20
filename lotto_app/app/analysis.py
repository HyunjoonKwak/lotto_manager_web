from collections import Counter, defaultdict
from app.models import db, Draw

NUM_RANGE = range(1, 46)

def load_all_numbers(include_bonus=False):
    rows = Draw.query.order_by(Draw.round.asc()).all()
    seqs = []
    for d in rows:
        nums = [d.n1, d.n2, d.n3, d.n4, d.n5, d.n6]
        if include_bonus:
            nums = nums + [d.bonus]
        seqs.append(nums)
    return seqs

def frequency(include_bonus=False):
    seqs = load_all_numbers(include_bonus)
    c = Counter()
    for nums in seqs:
        c.update(nums)
    # 1~45 모두 채워서 반환
    return {n: c.get(n, 0) for n in NUM_RANGE}

def hot_cold(top_k=10, include_bonus=False):
    freq = frequency(include_bonus)
    items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    hot = items[:top_k]
    cold = sorted(items, key=lambda x: (x[1], x[0]))[:top_k]
    return {"hot": hot, "cold": cold}

def pair_frequency():
    """두 수 페어(순서 무시) 빈도"""
    from itertools import combinations
    seqs = load_all_numbers(include_bonus=False)
    c = Counter()
    for nums in seqs:
        for a,b in combinations(sorted(nums), 2):
            c[(a,b)] += 1
    return c

def summary(top_k=10):
    freq_main = frequency(include_bonus=False)
    hc = hot_cold(top_k=top_k, include_bonus=False)
    pairs = pair_frequency()
    top_pairs = sorted(pairs.items(), key=lambda x: (-x[1], x[0]))[:top_k]
    return {
        "count_draws": Draw.query.count(),
        "frequency": freq_main,
        "hot": hc["hot"],
        "cold": hc["cold"],
        "top_pairs": [ (list(p), cnt) for p,cnt in top_pairs ],
    }
