#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime
from collections import Counter, defaultdict
import itertools
import json

class LottoAdvancedAnalyzer:
    def __init__(self, db_path):
        self.db_path = db_path

    def create_analysis_tables(self):
        """고급 분석용 테이블 생성"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 번호 조합 분석 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS number_combinations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    combination_type INTEGER NOT NULL,  -- 2, 3, 4개 조합
                    numbers TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    last_drawn TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(combination_type, numbers)
                )
            """)

            # 구매 기록 테이블 (개선)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw_no INTEGER NOT NULL,
                    numbers TEXT NOT NULL,
                    purchase_type TEXT DEFAULT 'manual',  -- manual, auto, semi_auto
                    algorithm_used TEXT,
                    purchase_amount INTEGER DEFAULT 1000,
                    matched_count INTEGER DEFAULT 0,
                    prize_amount INTEGER DEFAULT 0,
                    result_analyzed BOOLEAN DEFAULT 0,
                    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 당첨 통계 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS winning_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_date TEXT NOT NULL,
                    total_purchases INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    total_won INTEGER DEFAULT 0,
                    match_5_plus_bonus INTEGER DEFAULT 0,
                    match_5 INTEGER DEFAULT 0,
                    match_4 INTEGER DEFAULT 0,
                    match_3 INTEGER DEFAULT 0,
                    best_algorithm TEXT,
                    roi_percentage REAL DEFAULT 0.0
                )
            """)

            conn.commit()
            conn.close()

            print("✅ 고급 분석 테이블 생성 완료")
            return True

        except Exception as e:
            print(f"❌ 테이블 생성 실패: {str(e)}")
            return False

    def analyze_number_combinations(self):
        """번호 조합 분석 (2개, 3개, 4개)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 모든 당첨번호 가져오기
            cursor.execute("""
                SELECT num1, num2, num3, num4, num5, num6, draw_no, draw_date
                FROM lotto_results
                ORDER BY draw_no DESC
            """)

            all_results = cursor.fetchall()

            if not all_results:
                print("❌ 분석할 데이터가 없습니다.")
                return False

            print(f"🔍 {len(all_results)}회차 조합 분석 중...")

            # 조합별 카운터
            combinations_2 = Counter()
            combinations_3 = Counter()
            combinations_4 = Counter()

            # 각 회차별 조합 분석
            for row in all_results:
                numbers = sorted(row[:6])
                draw_no = row[6]
                draw_date = row[7]

                # 2개 조합
                for combo in itertools.combinations(numbers, 2):
                    combinations_2[combo] += 1

                # 3개 조합
                for combo in itertools.combinations(numbers, 3):
                    combinations_3[combo] += 1

                # 4개 조합
                for combo in itertools.combinations(numbers, 4):
                    combinations_4[combo] += 1

            # 데이터베이스에 저장
            cursor.execute("DELETE FROM number_combinations")  # 기존 데이터 삭제

            # 2개 조합 저장 (상위 100개)
            for combo, freq in combinations_2.most_common(100):
                numbers_str = ','.join(map(str, combo))
                cursor.execute("""
                    INSERT INTO number_combinations
                    (combination_type, numbers, frequency)
                    VALUES (2, ?, ?)
                """, (numbers_str, freq))

            # 3개 조합 저장 (상위 100개)
            for combo, freq in combinations_3.most_common(100):
                numbers_str = ','.join(map(str, combo))
                cursor.execute("""
                    INSERT INTO number_combinations
                    (combination_type, numbers, frequency)
                    VALUES (3, ?, ?)
                """, (numbers_str, freq))

            # 4개 조합 저장 (상위 50개)
            for combo, freq in combinations_4.most_common(50):
                numbers_str = ','.join(map(str, combo))
                cursor.execute("""
                    INSERT INTO number_combinations
                    (combination_type, numbers, frequency)
                    VALUES (4, ?, ?)
                """, (numbers_str, freq))

            conn.commit()
            conn.close()

            # 결과 출력
            print(f"\n🔥 빈출 2개 조합 TOP 10:")
            for i, (combo, freq) in enumerate(combinations_2.most_common(10), 1):
                print(f"   {i:2d}. {combo[0]:2d}-{combo[1]:2d}: {freq}회")

            print(f"\n🔥 빈출 3개 조합 TOP 10:")
            for i, (combo, freq) in enumerate(combinations_3.most_common(10), 1):
                combo_str = '-'.join([f'{n:2d}' for n in combo])
                print(f"   {i:2d}. {combo_str}: {freq}회")

            print(f"\n🔥 빈출 4개 조합 TOP 5:")
            for i, (combo, freq) in enumerate(combinations_4.most_common(5), 1):
                combo_str = '-'.join([f'{n:2d}' for n in combo])
                print(f"   {i:2d}. {combo_str}: {freq}회")

            return True

        except Exception as e:
            print(f"❌ 조합 분석 실패: {str(e)}")
            return False

    def generate_smart_recommendations(self):
        """스마트 추천 (조합 분석 기반)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 빈출 2개 조합 가져오기
            cursor.execute("""
                SELECT numbers, frequency FROM number_combinations
                WHERE combination_type = 2
                ORDER BY frequency DESC LIMIT 20
            """)

            top_pairs = cursor.fetchall()

            if not top_pairs:
                print("❌ 조합 데이터가 없습니다. 먼저 조합 분석을 실행하세요.")
                return []

            # 빈출 조합 기반 추천
            recommendations = []

            # 1. 최고 빈출 조합 기반 추천
            best_pair = top_pairs[0][0].split(',')
            base_numbers = [int(x) for x in best_pair]

            # 나머지 4개 번호를 빈출 번호에서 선택
            cursor.execute("""
                SELECT number FROM number_frequency
                WHERE number NOT IN (?, ?)
                ORDER BY frequency DESC LIMIT 10
            """, tuple(base_numbers))

            candidate_numbers = [row[0] for row in cursor.fetchall()]

            if len(candidate_numbers) >= 4:
                import random
                remaining = random.sample(candidate_numbers, 4)
                smart_numbers = sorted(base_numbers + remaining)

                recommendations.append({
                    'algorithm': 'smart_combination',
                    'name': '스마트 조합',
                    'numbers': smart_numbers,
                    'confidence': 80,
                    'reason': f'최고 빈출 조합 {base_numbers[0]}-{base_numbers[1]} 기반'
                })

            # 2. 균형 조합 (빈출 + 미출현)
            cursor.execute("""
                SELECT number FROM number_frequency
                ORDER BY not_drawn_weeks DESC LIMIT 3
            """)
            overdue_numbers = [row[0] for row in cursor.fetchall()]

            cursor.execute("""
                SELECT number FROM number_frequency
                ORDER BY frequency DESC LIMIT 3
            """)
            frequent_numbers = [row[0] for row in cursor.fetchall()]

            if len(overdue_numbers) >= 3 and len(frequent_numbers) >= 3:
                balanced_numbers = sorted(overdue_numbers + frequent_numbers)

                recommendations.append({
                    'algorithm': 'balanced_smart',
                    'name': '균형 스마트',
                    'numbers': balanced_numbers,
                    'confidence': 75,
                    'reason': '빈출번호 3개 + 미출현번호 3개 조합'
                })

            conn.close()
            return recommendations

        except Exception as e:
            print(f"❌ 스마트 추천 실패: {str(e)}")
            return []

    def analyze_purchase_performance(self):
        """구매 성과 분석"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 전체 구매 통계
            cursor.execute("""
                SELECT
                    COUNT(*) as total_purchases,
                    SUM(purchase_amount) as total_spent,
                    SUM(prize_amount) as total_won,
                    SUM(CASE WHEN matched_count = 6 THEN 1 ELSE 0 END) as jackpot,
                    SUM(CASE WHEN matched_count = 5 THEN 1 ELSE 0 END) as match_5,
                    SUM(CASE WHEN matched_count = 4 THEN 1 ELSE 0 END) as match_4,
                    SUM(CASE WHEN matched_count = 3 THEN 1 ELSE 0 END) as match_3
                FROM purchase_records
            """)

            stats = cursor.fetchone()

            if stats and stats[0] > 0:
                total_purchases, total_spent, total_won = stats[:3]
                jackpot, match_5, match_4, match_3 = stats[3:]

                roi = ((total_won - total_spent) / max(1, total_spent)) * 100

                print(f"\n💰 구매 성과 분석:")
                print(f"   총 구매 횟수: {total_purchases:,}회")
                print(f"   총 구매 금액: {total_spent:,}원")
                print(f"   총 당첨 금액: {total_won:,}원")
                print(f"   수익률: {roi:+.2f}%")
                print(f"\n🎯 당첨 통계:")
                print(f"   1등: {jackpot}회")
                print(f"   2등: {match_5}회")
                print(f"   3등: {match_4}회")
                print(f"   4등: {match_3}회")

                # 알고리즘별 성과
                cursor.execute("""
                    SELECT algorithm_used,
                           COUNT(*) as count,
                           AVG(matched_count) as avg_match,
                           SUM(prize_amount) as total_prize
                    FROM purchase_records
                    WHERE algorithm_used IS NOT NULL
                    GROUP BY algorithm_used
                    ORDER BY avg_match DESC
                """)

                algo_stats = cursor.fetchall()
                if algo_stats:
                    print(f"\n🤖 알고리즘별 성과:")
                    for algo, count, avg_match, total_prize in algo_stats:
                        print(f"   {algo}: 평균 {avg_match:.1f}개 맞춤 ({count}회, {total_prize:,}원)")

            else:
                print("📊 구매 기록이 없습니다.")

            conn.close()
            return True

        except Exception as e:
            print(f"❌ 성과 분석 실패: {str(e)}")
            return False

def main():
    print("🧠 로또 고급 분석 시스템")
    print("=" * 50)

    db_path = '/volume1/web/lotto/database/lotto.db'
    analyzer = LottoAdvancedAnalyzer(db_path)

    print("1️⃣ 고급 분석 테이블 생성...")
    analyzer.create_analysis_tables()

    print("\n2️⃣ 번호 조합 분석...")
    analyzer.analyze_number_combinations()

    print("\n3️⃣ 스마트 추천 생성...")
    recommendations = analyzer.generate_smart_recommendations()

    if recommendations:
        print(f"\n🎯 스마트 추천 결과:")
        for i, rec in enumerate(recommendations, 1):
            numbers_str = ' - '.join([f'{n:2d}' for n in rec['numbers']])
            print(f"{i}. [{rec['name']}] 신뢰도 {rec['confidence']}%")
            print(f"   번호: {numbers_str}")
            print(f"   이유: {rec['reason']}")
            print()

    print("4️⃣ 구매 성과 분석...")
    analyzer.analyze_purchase_performance()

    print("\n🎉 고급 분석 완료!")

if __name__ == "__main__":
    main()
