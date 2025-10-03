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


def generate_recommendation_insights(user_id: int) -> Dict:
    """
    Generate actionable insights for improving user's recommendation strategy.
    Returns hints based on purchase history and winning patterns.
    """
    from ..models import Purchase
    from ..extensions import db

    # Get user's purchase history
    all_purchases = Purchase.query.filter_by(
        user_id=user_id,
        status='PURCHASED'
    ).all()

    if not all_purchases:
        return {
            'insights': [],
            'recommendations': [],
            'warnings': []
        }

    # Analyze patterns
    total_purchases = len(all_purchases)
    winning_purchases = [p for p in all_purchases if p.winning_rank]

    # Source method analysis
    source_counter = Counter(p.source for p in all_purchases)
    winning_source_counter = Counter(p.source for p in winning_purchases)

    # Number pattern analysis
    all_numbers = Counter()
    for p in all_purchases:
        all_numbers.update(p.numbers_list())

    insights = []
    recommendations = []
    warnings = []

    # Insight 1: Source method effectiveness
    if winning_purchases and total_purchases >= 10:
        for source, count in winning_source_counter.most_common(1):
            source_name = {'ai': 'AI 추천', 'manual': '수동 입력', 'random': '랜덤', 'qr': 'QR'}.get(source, source)
            win_rate = (count / winning_source_counter.total()) * 100
            if win_rate > 50:
                insights.append(f"💡 '{source_name}' 방식이 당첨률이 높습니다 ({win_rate:.1f}%)")

    # Insight 2: Number concentration
    most_common_numbers = all_numbers.most_common(10)
    if most_common_numbers:
        top_number, top_count = most_common_numbers[0]
        if top_count > total_purchases * 0.5:
            warnings.append(f"⚠️ {top_number}번이 너무 자주 선택되었습니다. 다양성이 필요할 수 있습니다.")

    # Insight 3: Purchase frequency
    if total_purchases >= 5:
        avg_per_round = total_purchases / len(set(p.purchase_round for p in all_purchases if p.purchase_round))
        if avg_per_round < 1:
            recommendations.append("📈 회차당 구매 횟수를 늘리면 당첨 확률이 높아집니다")
        elif avg_per_round > 5:
            recommendations.append("💰 회차당 구매가 많습니다. 전략적 선택이 필요할 수 있습니다")

    # Insight 4: Winning pattern hints
    winning_patterns = analyze_winning_patterns(user_id)
    if winning_patterns['total_wins'] > 0:
        best_pattern = max(winning_patterns['winning_patterns'].items(), key=lambda x: x[1], default=None)
        if best_pattern:
            pattern_name, pattern_count = best_pattern
            insights.append(f"🎯 당첨 이력에서 '{pattern_name}' 패턴이 효과적이었습니다")

    # Insight 5: Number range balance
    low = sum(1 for num, count in all_numbers.items() if num <= 15)
    mid = sum(1 for num, count in all_numbers.items() if 16 <= num <= 30)
    high = sum(1 for num, count in all_numbers.items() if num >= 31)
    total_nums = low + mid + high

    if total_nums > 0:
        low_pct = (low / total_nums) * 100
        high_pct = (high / total_nums) * 100

        if low_pct > 50:
            recommendations.append("🔄 저구간(1-15) 번호가 많습니다. 중고구간 번호를 추가해보세요")
        elif high_pct > 50:
            recommendations.append("🔄 고구간(31-45) 번호가 많습니다. 저중구간 번호를 추가해보세요")

    # Default recommendations if no data
    if not insights and not recommendations:
        recommendations.append("📊 더 많은 구매 데이터가 쌓이면 맞춤 분석을 제공합니다")

    return {
        'insights': insights[:3],  # Top 3 insights
        'recommendations': recommendations[:3],  # Top 3 recommendations
        'warnings': warnings[:2]  # Top 2 warnings
    }


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
