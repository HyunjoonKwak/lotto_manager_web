"""
Lottery number frequency and pattern analysis service.
"""
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
from ..models import Draw


def get_number_frequency(limit: int = None) -> Dict[int, int]:
    """Get frequency of each number across all draws."""
    query = Draw.query.order_by(Draw.round.desc())
    if limit:
        query = query.limit(limit)

    draws = query.all()
    frequency = Counter()

    for draw in draws:
        numbers = draw.numbers_list()
        for num in numbers:
            frequency[num] += 1

    return dict(frequency)


def get_most_frequent_numbers(count: int = 10, limit: int = None) -> List[Tuple[int, int]]:
    """Get most frequently drawn numbers."""
    frequency = get_number_frequency(limit)
    return Counter(frequency).most_common(count)


def get_least_frequent_numbers(count: int = 10, limit: int = None) -> List[Tuple[int, int]]:
    """Get least frequently drawn numbers."""
    frequency = get_number_frequency(limit)
    return Counter(frequency).most_common()[:-count-1:-1]


def get_number_combinations(count: int = 10, limit: int = None) -> List[Tuple[Tuple[int, ...], int]]:
    """Get most frequent number combinations (pairs)."""
    query = Draw.query.order_by(Draw.round.desc())
    if limit:
        query = query.limit(limit)

    draws = query.all()
    combinations = Counter()

    for draw in draws:
        numbers = draw.numbers_list()
        # Generate all pairs from the 6 numbers
        for i in range(len(numbers)):
            for j in range(i + 1, len(numbers)):
                pair = tuple(sorted([numbers[i], numbers[j]]))
                combinations[pair] += 1

    return combinations.most_common(count)


def analyze_patterns(limit: int = None) -> Dict:
    """Analyze various patterns in lottery draws."""
    query = Draw.query.order_by(Draw.round.desc())
    if limit:
        query = query.limit(limit)

    draws = query.all()

    # Pattern analysis
    odd_even_patterns = Counter()
    sum_ranges = Counter()
    consecutive_counts = Counter()

    for draw in draws:
        numbers = sorted(draw.numbers_list())

        # Odd/Even pattern
        odd_count = sum(1 for n in numbers if n % 2 == 1)
        even_count = 6 - odd_count
        odd_even_patterns[f"{odd_count}홀/{even_count}짝"] += 1

        # Sum range analysis
        total_sum = sum(numbers)
        if total_sum <= 120:
            sum_ranges["낮음(~120)"] += 1
        elif total_sum <= 150:
            sum_ranges["중간(121~150)"] += 1
        elif total_sum <= 180:
            sum_ranges["높음(151~180)"] += 1
        else:
            sum_ranges["매우높음(181~)"] += 1

        # Consecutive numbers count
        consecutive = 0
        for i in range(len(numbers) - 1):
            if numbers[i + 1] - numbers[i] == 1:
                consecutive += 1
        consecutive_counts[consecutive] += 1

    return {
        "odd_even_patterns": dict(odd_even_patterns.most_common()),
        "sum_ranges": dict(sum_ranges.most_common()),
        "consecutive_counts": dict(consecutive_counts.most_common()),
        "total_analyzed": len(draws)
    }


def get_recommendation_reasons(recommended_numbers: List[int], limit: int = 50) -> List[str]:
    """Generate reasons for recommended numbers based on analysis."""
    reasons = []

    # Get frequency data
    frequency = get_number_frequency(limit)
    most_frequent = [num for num, _ in get_most_frequent_numbers(10, limit)]
    least_frequent = [num for num, _ in get_least_frequent_numbers(10, limit)]

    # Analyze recommended numbers
    rec_set = set(recommended_numbers)

    # Check frequency balance
    high_freq = sum(1 for num in recommended_numbers if num in most_frequent[:5])
    low_freq = sum(1 for num in recommended_numbers if num in least_frequent[:5])

    if high_freq > 0:
        reasons.append(f"최다 빈출번호 {high_freq}개 포함 (균형잡힌 선택)")

    if low_freq > 0:
        reasons.append(f"최소 빈출번호 {low_freq}개 포함 (반전 기대)")

    # Check odd/even balance
    odd_count = sum(1 for n in recommended_numbers if n % 2 == 1)
    even_count = 6 - odd_count
    if abs(odd_count - even_count) <= 2:
        reasons.append(f"홀짝 균형 ({odd_count}홀/{even_count}짝)")

    # Check number range distribution
    ranges = [0, 0, 0, 0]  # 1-10, 11-20, 21-30, 31-45
    for num in recommended_numbers:
        if num <= 10:
            ranges[0] += 1
        elif num <= 20:
            ranges[1] += 1
        elif num <= 30:
            ranges[2] += 1
        else:
            ranges[3] += 1

    distributed_ranges = sum(1 for r in ranges if r > 0)
    if distributed_ranges >= 3:
        reasons.append(f"번호 범위 분산 ({distributed_ranges}개 구간)")

    # Check sum range
    total_sum = sum(recommended_numbers)
    if 120 <= total_sum <= 180:
        reasons.append(f"합계 적정범위 ({total_sum})")

    # Check consecutive numbers
    sorted_nums = sorted(recommended_numbers)
    consecutive = sum(1 for i in range(len(sorted_nums) - 1) if sorted_nums[i + 1] - sorted_nums[i] == 1)
    if consecutive == 0:
        reasons.append("연속번호 없음 (분산효과)")
    elif consecutive <= 2:
        reasons.append(f"연속번호 {consecutive}개 (적절한 클러스터)")

    return reasons[:5]  # Return top 5 reasons


def get_hot_cold_analysis(limit: int = 50) -> Dict:
    """Get hot and cold number analysis for recent draws."""
    frequency = get_number_frequency(limit)

    # Calculate average frequency
    total_frequency = sum(frequency.values())
    avg_frequency = total_frequency / 45 if total_frequency > 0 else 0

    hot_numbers = []
    cold_numbers = []
    normal_numbers = []

    for num in range(1, 46):
        freq = frequency.get(num, 0)
        if freq > avg_frequency * 1.2:
            hot_numbers.append((num, freq))
        elif freq < avg_frequency * 0.8:
            cold_numbers.append((num, freq))
        else:
            normal_numbers.append((num, freq))

    return {
        "hot_numbers": sorted(hot_numbers, key=lambda x: x[1], reverse=True),
        "cold_numbers": sorted(cold_numbers, key=lambda x: x[1]),
        "normal_numbers": sorted(normal_numbers, key=lambda x: x[1], reverse=True),
        "avg_frequency": avg_frequency,
        "analyzed_draws": limit
    }
