#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime
from collections import Counter
import itertools

class LottoAnalyzer:
    def __init__(self, db_path):
        self.db_path = db_path

    def analyze_number_frequency(self):
        """번호별 출현 빈도 분석"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT num1, num2, num3, num4, num5, num6, bonus_num, draw_no
                FROM lotto_results
                ORDER BY draw_no DESC
            """)

            results = cursor.fetchall()

            if not results:
                print("❌ 분석할 데이터가 없습니다.")
                return False

            print(f"📊 {len(results)}회차 데이터 분석 중...")

            # 번호별 빈도 계산
            number_freq = Counter()
            bonus_freq = Counter()
            last_drawn = {}

            for row in results:
                numbers = list(row[:6])
                bonus = row[6]
                draw_no = row[7]

                # 일반 번호 빈도
                for num in numbers:
                    number_freq[num] += 1
                    last_drawn[num] = draw_no

                # 보너스 번호 빈도
                bonus_freq[bonus] += 1
                if bonus not in last_drawn:
                    last_drawn[bonus] = draw_no

            # 미출현 주차 계산
            latest_draw = results[0][7] if results else 0
            not_drawn_weeks = {}
            for num in range(1, 46):
                if num in last_drawn:
                    not_drawn_weeks[num] = latest_draw - last_drawn[num]
                else:
                    not_drawn_weeks[num] = latest_draw

            # 데이터베이스 업데이트
            for num in range(1, 46):
                cursor.execute("""
                    UPDATE number_frequency SET
                    frequency = ?,
                    last_drawn = ?,
                    not_drawn_weeks = ?,
                    bonus_frequency = ?,
                    updated_at = ?
                    WHERE number = ?
                """, (
                    number_freq.get(num, 0),
                    str(last_drawn.get(num, '')),
                    not_drawn_weeks.get(num, 0),
                    bonus_freq.get(num, 0),
                    datetime.now().isoformat(),
                    num
                ))

            conn.commit()
            conn.close()

            # 결과 출력
            print(f"\n🔥 빈출 번호 TOP 10:")
            most_frequent = number_freq.most_common(10)
            for i, (num, freq) in enumerate(most_frequent, 1):
                percentage = (freq / len(results)) * 100
                print(f"   {i:2d}. {num:2d}번: {freq:2d}회 ({percentage:.1f}%)")

            print(f"\n❄️ 오랫동안 안 나온 번호 TOP 10:")
            sorted_not_drawn = sorted(not_drawn_weeks.items(), key=lambda x: x[1], reverse=True)
            for i, (num, weeks) in enumerate(sorted_not_drawn[:10], 1):
                print(f"   {i:2d}. {num:2d}번: {weeks}주차 전")

            return True

        except Exception as e:
            print(f"❌ 번호 빈도 분석 실패: {str(e)}")
            return False

    def analyze_patterns(self):
        """추가 패턴 분석"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 연속번호 패턴 분석
            cursor.execute("""
                SELECT num1, num2, num3, num4, num5, num6, draw_no
                FROM lotto_results
                ORDER BY draw_no DESC LIMIT 50
            """)

            consecutive_count = 0
            total_draws = 0

            for row in cursor.fetchall():
                numbers = sorted(row[:6])
                total_draws += 1

                # 연속번호 체크
                for i in range(len(numbers) - 1):
                    if numbers[i+1] - numbers[i] == 1:
                        consecutive_count += 1
                        break

            consecutive_rate = (consecutive_count / total_draws) * 100 if total_draws > 0 else 0

            print(f"\n📈 패턴 분석 결과:")
            print(f"   연속번호 포함 비율: {consecutive_rate:.1f}% ({consecutive_count}/{total_draws})")

            # 홀짝 분석
            cursor.execute("""
                SELECT num1, num2, num3, num4, num5, num6
                FROM lotto_results
                ORDER BY draw_no DESC LIMIT 20
            """)

            odd_even_patterns = {'홀수우세': 0, '짝수우세': 0, '균형': 0}

            for row in cursor.fetchall():
                numbers = row[:6]
                odd_count = sum(1 for num in numbers if num % 2 == 1)

                if odd_count >= 4:
                    odd_even_patterns['홀수우세'] += 1
                elif odd_count <= 2:
                    odd_even_patterns['짝수우세'] += 1
                else:
                    odd_even_patterns['균형'] += 1

            print(f"   홀짝 패턴 (최근 20회):")
            for pattern, count in odd_even_patterns.items():
                print(f"     {pattern}: {count}회")

            conn.close()
            return True

        except Exception as e:
            print(f"❌ 패턴 분석 실패: {str(e)}")
            return False

def main():
    print("📊 로또 번호 분석 엔진")
    print("=" * 50)

    db_path = '/volume1/web/lotto/database/lotto.db'
    analyzer = LottoAnalyzer(db_path)

    print("1️⃣ 번호별 출현 빈도 분석...")
    if analyzer.analyze_number_frequency():
        print("2️⃣ 패턴 분석...")
        analyzer.analyze_patterns()

    print("\n🎉 로또 번호 분석 완료!")

if __name__ == "__main__":
    main()
