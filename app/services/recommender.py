import random
from collections import Counter, defaultdict
from typing import Iterable, List, Optional, Dict, Tuple
from sqlalchemy import and_


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


def analyze_winning_patterns(user_id: int) -> Dict:
    """
    Analyze winning patterns from user's purchase history.
    Returns insights that can be used for smarter recommendations.
    """
    from ..models import Purchase, Draw
    from ..extensions import db

    # Get user's winning purchases
    winning_purchases = Purchase.query.filter(
        and_(
            Purchase.user_id == user_id,
            Purchase.winning_rank.isnot(None),
            Purchase.result_checked == True
        )
    ).all()

    if not winning_purchases:
        return {
            'winning_numbers': [],
            'winning_patterns': {},
            'successful_methods': {},
            'winning_rounds': [],
            'total_wins': 0,
            'best_rank': None
        }

    # Analyze winning numbers frequency
    winning_numbers_freq = Counter()
    winning_patterns = defaultdict(int)
    successful_methods = defaultdict(list)
    winning_rounds = []

    for purchase in winning_purchases:
        numbers = purchase.numbers_list()
        winning_numbers_freq.update(numbers)
        winning_rounds.append(purchase.purchase_round)

        # Analyze patterns
        odd_count = sum(1 for n in numbers if n % 2 == 1)
        even_count = 6 - odd_count
        winning_patterns[f"{odd_count}홀{even_count}짝"] += 1

        # Track successful methods
        if purchase.purchase_method:
            successful_methods[purchase.purchase_method].append({
                'rank': purchase.winning_rank,
                'numbers': numbers,
                'round': purchase.purchase_round
            })

    return {
        'winning_numbers': winning_numbers_freq.most_common(),
        'winning_patterns': dict(winning_patterns),
        'successful_methods': dict(successful_methods),
        'winning_rounds': winning_rounds,
        'total_wins': len(winning_purchases),
        'best_rank': min(p.winning_rank for p in winning_purchases)
    }


def get_user_lucky_numbers(user_id: int, top_n: int = 10) -> List[int]:
    """Get user's most frequently winning numbers."""
    patterns = analyze_winning_patterns(user_id)
    winning_numbers = patterns['winning_numbers']
    return [num for num, freq in winning_numbers[:top_n]]


def enhanced_auto_recommend(draw_numbers: Iterable[List[int]], user_id: Optional[int] = None, count: int = 3) -> Tuple[List[List[int]], List[List[str]]]:
    """
    Enhanced recommendation system that considers:
    1. Historical frequency (기본)
    2. User's winning patterns (당첨 이력 기반)
    3. Balanced odd/even distribution
    4. Number range distribution
    """
    # Basic frequency analysis
    freq = Counter(n for seq in draw_numbers for n in seq)

    # User's winning pattern analysis
    user_patterns = {}
    user_lucky_numbers = []
    if user_id:
        user_patterns = analyze_winning_patterns(user_id)
        user_lucky_numbers = get_user_lucky_numbers(user_id, 15)

    recommendations = []
    reasons = []

    for i in range(count):
        picks = set()
        pick_reasons = []

        # Strategy 1: Include user's lucky numbers (if available)
        if user_lucky_numbers and i == 0:
            # First recommendation: heavily favor user's winning numbers
            lucky_pool = user_lucky_numbers[:8]
            if len(lucky_pool) >= 3:
                selected_lucky = random.sample(lucky_pool, min(3, len(lucky_pool)))
                picks.update(selected_lucky)
                pick_reasons.append(f"행운의 번호 {len(selected_lucky)}개 포함")

        # Strategy 2: Frequency-based selection with user bias
        pool = list(range(1, 46))
        weights = []

        for n in pool:
            base_weight = freq.get(n, 1)

            # Boost weight for user's lucky numbers
            if n in user_lucky_numbers:
                base_weight *= 1.5

            weights.append(base_weight)

        # Fill remaining slots
        candidates = [n for n in pool if n not in picks]
        candidate_weights = [weights[n-1] for n in candidates]

        while len(picks) < 6:
            if not candidates:
                break
            selected = random.choices(candidates, weights=candidate_weights, k=1)[0]
            picks.add(selected)

            # Remove selected number from candidates
            idx = candidates.index(selected)
            candidates.pop(idx)
            candidate_weights.pop(idx)

        # Ensure we have exactly 6 numbers
        if len(picks) < 6:
            remaining = [n for n in range(1, 46) if n not in picks]
            picks.update(random.sample(remaining, 6 - len(picks)))

        final_picks = sorted(list(picks))

        # Generate reasons
        if not pick_reasons:
            # Analyze the recommendation
            high_freq_count = sum(1 for n in final_picks if freq.get(n, 0) > 30)
            if high_freq_count >= 3:
                pick_reasons.append(f"빈출번호 {high_freq_count}개 포함")

            odd_count = sum(1 for n in final_picks if n % 2 == 1)
            if 2 <= odd_count <= 4:
                pick_reasons.append(f"홀짝 균형 ({odd_count}홀{6-odd_count}짝)")

            # Check number range distribution
            low_count = sum(1 for n in final_picks if n <= 15)
            mid_count = sum(1 for n in final_picks if 16 <= n <= 30)
            high_count = sum(1 for n in final_picks if n >= 31)

            if min(low_count, mid_count, high_count) >= 1:
                pick_reasons.append("구간별 균형 배치")

        if not pick_reasons:
            pick_reasons.append("빈도 기반 추천")

        recommendations.append(final_picks)
        reasons.append(pick_reasons)

    return recommendations, reasons
