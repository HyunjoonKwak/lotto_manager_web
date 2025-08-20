import random
from typing import List, Tuple
from app.models import db, Recommendation, Draw
from app.analysis import frequency, pair_frequency, hot_cold

def _score_set(nums: List[int], freq_map: dict, pair_map: dict) -> float:
    """간단 가중치: 단일 빈출합 + 페어 시너지"""
    base = sum(freq_map.get(n, 0) for n in nums)
    # 페어 보너스
    pairs = []
    for i in range(len(nums)):
        for j in range(i+1, len(nums)):
            a,b = sorted((nums[i], nums[j]))
            pairs.append((a,b))
    pair_bonus = sum(pair_map.get((a,b), 0) for (a,b) in pairs)
    return base + 0.1 * pair_bonus

def _diverse_pick(candidates: List[int], need: int, exclude=set()):
    picked = []
    pool = [n for n in candidates if n not in exclude]
    # 구간 다양화(1~45를 6구간으로 보고 각 구간에서 골고루 뽑기)
    buckets = {i: [] for i in range(6)}
    for n in pool:
        buckets[min((n-1)//8, 5)].append(n)
    # 라운드 로빈으로 뽑기
    bkeys = list(buckets.keys())
    idx = 0
    while len(picked) < need and any(buckets[k] for k in bkeys):
        b = bkeys[idx % len(bkeys)]
        if buckets[b]:
            picked.append(buckets[b].pop(0))
        idx += 1
    # 남으면 남은 pool에서 채우기
    if len(picked) < need:
        rest = [n for n in pool if n not in picked]
        picked += rest[:(need-len(picked))]
    return sorted(picked)[:need]

def generate_full_and_semi(target_round: int):
    """
    반환: (full_list, semi_list)
    full_list: [ [6개], ... ] 5세트
    semi_list: [ [3개], ... ] 5세트
    """
    freq_map = frequency(include_bonus=False)
    pair_map = pair_frequency()
    hc = hot_cold(top_k=20, include_bonus=False)
    hot_nums = [n for n,_cnt in hc["hot"]]

    full_sets = []
    semi_sets = []

    # 1) 완전 5세트: 핫 기반 + 다양성 + 랜덤 보정
    for _ in range(12):  # 후보 많이 만든 뒤 상위 5개만 선택
        # 핵심시드 3개: hot 상위에서 다양하게
        seed = _diverse_pick(hot_nums, 3)
        # 보정 3개: 전체에서 랜덤 + 다양성
        remain_pool = [n for n in range(1,46) if n not in seed]
        random.shuffle(remain_pool)
        add = _diverse_pick(remain_pool, 3)
        cand = sorted(set(seed + add))[:6]
        if len(cand) == 6:
            full_sets.append(cand)

    # 점수 상위 5개만
    full_sets = sorted({tuple(s) for s in full_sets})  # 중복 제거
    full_scored = [ (list(s), _score_set(list(s), freq_map, pair_map)) for s in full_sets ]
    full_scored.sort(key=lambda x: (-x[1], x[0]))
    full_top5 = [s for s,_ in full_scored[:5]]

    # 2) 반자동 5세트(3개만): hot에서 구간 다양성 보장
    for i in range(5):
        semi = _diverse_pick(hot_nums, 3, exclude=set(sum(full_top5[:i], [])))
        if len(semi) < 3:
            semi = _diverse_pick(hot_nums, 3)
        semi_sets.append(semi)

    # DB에 저장
    for nums in full_top5:
        r = Recommendation(round=target_round, kind="full",
                           numbers=",".join(map(str, nums)),
                           confidence=1.0, reason="freq+pair mixed")
        db.session.add(r)
    for nums in semi_sets:
        r = Recommendation(round=target_round, kind="semi",
                           numbers=",".join(map(str, nums)),
                           confidence=0.8, reason="hot-diversity")
        db.session.add(r)
    db.session.commit()

    return full_top5, semi_sets
