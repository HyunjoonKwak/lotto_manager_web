#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import random
from datetime import datetime
import math

class LottoRecommenderEnhanced:
    def __init__(self, db_path):
        self.db_path = db_path

    def get_number_statistics(self):
        """번호별 통계 데이터 가져오기"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT number, frequency, not_drawn_weeks, bonus_frequency
                FROM number_frequency
                ORDER BY number
            """)

            stats = {}
            for row in cursor.fetchall():
                num, freq, not_drawn, bonus_freq = row
                stats[num] = {
                    'frequency': freq,
                    'not_drawn_weeks': not_drawn,
                    'bonus_frequency': bonus_freq
                }

            cursor.execute("SELECT COUNT(*) FROM lotto_results")
            total_draws = cursor.fetchone()[0]

            conn.close()
            return stats, total_draws

        except Exception as e:
            print(f"❌ 통계 데이터 조회 실패: {str(e)}")
            return {}, 0

    def frequency_based_recommendation(self):
        """빈도 기반 추천"""
        stats, total_draws = self.get_number_statistics()

        if not stats or total_draws == 0:
            return sorted(random.sample(range(1, 46), 6))

        # 빈도 기반 가중치
        weighted_numbers = []
        for num in range(1, 46):
            frequency = stats.get(num, {}).get('frequency', 0)
            weight = max(1, frequency)
            weighted_numbers.extend([num] * weight)

        selected = []
        attempts = 0
        while len(selected) < 6 and attempts < 1000:
            num = random.choice(weighted_numbers)
            if num not in selected:
                selected.append(num)
            attempts += 1

        while len(selected) < 6:
            num = random.randint(1, 45)
            if num not in selected:
                selected.append(num)

        return sorted(selected)

    def overdue_based_recommendation(self):
        """미출현 기간 기반 추천"""
        stats, total_draws = self.get_number_statistics()

        if not stats:
            return sorted(random.sample(range(1, 46), 6))

        # 미출현 기간 기반 가중치
        weighted_numbers = []
        for num in range(1, 46):
            not_drawn_weeks = stats.get(num, {}).get('not_drawn_weeks', 0)
            weight = max(1, not_drawn_weeks // 2)
            weighted_numbers.extend([num] * weight)

        selected = []
        attempts = 0
        while len(selected) < 6 and attempts < 1000:
            num = random.choice(weighted_numbers)
            if num not in selected:
                selected.append(num)
            attempts += 1

        while len(selected) < 6:
            num = random.randint(1, 45)
            if num not in selected:
                selected.append(num)

        return sorted(selected)

    def hybrid_recommendation(self):
        """하이브리드 추천"""
        stats, total_draws = self.get_number_statistics()

        if not stats or total_draws == 0:
            return sorted(random.sample(range(1, 46), 6))

        scores = {}
        max_freq = max(stats[num].get('frequency', 0) for num in range(1, 46))
        max_not_drawn = max(stats[num].get('not_drawn_weeks', 0) for num in range(1, 46))

        for num in range(1, 46):
            frequency = stats.get(num, {}).get('frequency', 0)
            not_drawn = stats.get(num, {}).get('not_drawn_weeks', 0)

            freq_score = (frequency / max(1, max_freq)) * 50 if max_freq > 0 else 0
            overdue_score = (not_drawn / max(1, max_not_drawn)) * 50 if max_not_drawn > 0 else 0

            scores[num] = freq_score * 0.3 + overdue_score * 0.7

        weighted_numbers = []
        for num, score in scores.items():
            weight = max(1, int(score * 2))
            weighted_numbers.extend([num] * weight)

        selected = []
        attempts = 0
        while len(selected) < 6 and attempts < 1000:
            num = random.choice(weighted_numbers)
            if num not in selected:
                selected.append(num)
            attempts += 1

        while len(selected) < 6:
            num = random.randint(1, 45)
            if num not in selected:
                selected.append(num)

        return sorted(selected)

    def balanced_recommendation(self):
        """균형 추천"""
        selected = []
        odds = [i for i in range(1, 46, 2)]
        evens = [i for i in range(2, 46, 2)]

        selected.extend(random.sample(odds, 3))
        selected.extend(random.sample(evens, 3))

        return sorted(selected)

    def smart_combination_recommendation(self):
        """스마트 조합 추천 (조합 분석 기반)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 빈출 2개 조합 가져오기
            cursor.execute("""
                SELECT numbers, frequency FROM number_combinations
                WHERE combination_type = 2
                ORDER BY frequency DESC LIMIT 5
            """)

            top_pairs = cursor.fetchall()

            if top_pairs:
                # 랜덤으로 하나의 조합 선택
                pair_str, freq = random.choice(top_pairs)
                base_numbers = [int(x) for x in pair_str.split(',')]

                # 나머지 4개 번호를 빈출 번호에서 선택
                cursor.execute("""
                    SELECT number FROM number_frequency
                    WHERE number NOT IN (?, ?)
                    ORDER BY frequency DESC LIMIT 15
                """, tuple(base_numbers))

                candidate_numbers = [row[0] for row in cursor.fetchall()]

                if len(candidate_numbers) >= 4:
                    remaining = random.sample(candidate_numbers, 4)
                    smart_numbers = sorted(base_numbers + remaining)
                    conn.close()
                    return smart_numbers

            conn.close()
            return self.hybrid_recommendation()

        except:
            return self.hybrid_recommendation()

    def generate_manual_recommendations(self):
        """수동 구매용 5가지 추천"""
        algorithms = {
            'frequency_based': ('빈도 기반', self.frequency_based_recommendation, 75),
            'overdue_based': ('미출현 기반', self.overdue_based_recommendation, 70),
            'hybrid': ('하이브리드', self.hybrid_recommendation, 85),
            'balanced': ('균형 조합', self.balanced_recommendation, 65),
            'smart_combination': ('스마트 조합', self.smart_combination_recommendation, 80)
        }

        recommendations = []

        for algo_key, (algo_name, algo_func, confidence) in algorithms.items():
            try:
                numbers = algo_func()
                reason = f"{algo_name} 분석으로 선정된 최적 조합"

                recommendations.append({
                    'algorithm': algo_key,
                    'name': algo_name,
                    'numbers': numbers,
                    'confidence': confidence,
                    'reason': reason,
                    'type': 'manual'
                })

            except Exception as e:
                print(f"⚠️ {algo_name} 알고리즘 실패: {str(e)}")
                numbers = sorted(random.sample(range(1, 46), 6))
                recommendations.append({
                    'algorithm': algo_key,
                    'name': f"{algo_name} (랜덤)",
                    'numbers': numbers,
                    'confidence': 50,
                    'reason': f"{algo_name} 실패로 랜덤 생성",
                    'type': 'manual'
                })

        return recommendations

    def generate_semi_auto_recommendations(self):
        """반자동 구매용 2가지 추천 (3개씩)"""
        stats, total_draws = self.get_number_statistics()

        if not stats:
            return []

        recommendations = []

        # 1. 최고 빈출 3개
        frequent_numbers = sorted(stats.items(), key=lambda x: x[1]['frequency'], reverse=True)
        top_frequent = [num for num, _ in frequent_numbers[:3]]

        recommendations.append({
            'algorithm': 'semi_auto_frequent',
            'name': '빈출 반자동',
            'numbers': top_frequent,
            'confidence': 85,
            'reason': '최고 빈출 번호 3개 고정',
            'type': 'semi_auto'
        })

        # 2. 최고 미출현 3개
        overdue_numbers = sorted(stats.items(), key=lambda x: x[1]['not_drawn_weeks'], reverse=True)
        top_overdue = [num for num, _ in overdue_numbers[:3]]

        recommendations.append({
            'algorithm': 'semi_auto_overdue',
            'name': '미출현 반자동',
            'numbers': top_overdue,
            'confidence': 80,
            'reason': '최장 미출현 번호 3개 고정',
            'type': 'semi_auto'
        })

        return recommendations

    def save_recommendations(self, recommendations):
        """추천 결과를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 다음 회차 번호 계산
            cursor.execute("SELECT MAX(draw_no) FROM lotto_results")
            result = cursor.fetchone()
            next_week = (result[0] if result and result[0] else 1000) + 1

            # 기존 추천 삭제
            cursor.execute("DELETE FROM recommended_numbers WHERE week_no = ?", (next_week,))

            for rec in recommendations:
                cursor.execute("""
                    INSERT INTO recommended_numbers
                    (week_no, numbers, algorithm, confidence_score, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    next_week,
                    ','.join(map(str, rec['numbers'])),
                    rec['algorithm'],
                    rec['confidence'],
                    rec['reason']
                ))

            conn.commit()
            conn.close()

            print(f"✅ {len(recommendations)}개 추천 결과 저장 완료 ({next_week}회차)")
            return True

        except Exception as e:
            print(f"❌ 추천 결과 저장 실패: {str(e)}")
            return False

def main():
    print("🤖 로또 번호 AI 추천 시스템 (강화버전)")
    print("=" * 60)

    db_path = '/volume1/web/lotto/database/lotto.db'
    recommender = LottoRecommenderEnhanced(db_path)

    print("🎯 수동 구매용 5가지 알고리즘 추천 중...")
    manual_recommendations = recommender.generate_manual_recommendations()

    print("🎲 반자동 구매용 2가지 추천 중...")
    semi_auto_recommendations = recommender.generate_semi_auto_recommendations()

    all_recommendations = manual_recommendations + semi_auto_recommendations

    print(f"\n🎲 추천 번호 결과 ({len(all_recommendations)}개 세트):")
    print("=" * 60)

    # 수동 추천 표시
    print("\n📝 수동 구매 추천 (5세트):")
    for i, rec in enumerate(manual_recommendations, 1):
        numbers_str = ' - '.join([f'{n:2d}' for n in rec['numbers']])
        print(f"{i}. [{rec['name']}] 신뢰도 {rec['confidence']}%")
        print(f"   번호: {numbers_str}")
        print(f"   이유: {rec['reason']}")
        print()

    # 반자동 추천 표시
    print("\n🎯 반자동 구매 추천 (2세트, 3개씩):")
    for i, rec in enumerate(semi_auto_recommendations, 1):
        numbers_str = ' - '.join([f'{n:2d}' for n in rec['numbers']])
        print(f"{i}. [{rec['name']}] 신뢰도 {rec['confidence']}%")
        print(f"   고정번호: {numbers_str} (나머지 3개 자동)")
        print(f"   이유: {rec['reason']}")
        print()

    # 데이터베이스에 저장
    recommender.save_recommendations(all_recommendations)

    print("🎉 로또 번호 추천 완료!")

if __name__ == "__main__":
    main()
