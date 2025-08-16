#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime
import json

class LottoPurchaseManager:
    def __init__(self, db_path):
        self.db_path = db_path

    def add_purchase_record(self, numbers, draw_no=None, algorithm='manual', purchase_type='manual'):
        """구매 기록 추가"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 다음 회차 번호 계산 (draw_no가 없으면)
            if draw_no is None:
                cursor.execute("SELECT MAX(draw_no) FROM lotto_results")
                result = cursor.fetchone()
                draw_no = (result[0] if result and result[0] else 1000) + 1

            numbers_str = ','.join(map(str, sorted(numbers)))

            cursor.execute("""
                INSERT INTO purchase_records
                (draw_no, numbers, purchase_type, algorithm_used, purchased_at)
                VALUES (?, ?, ?, ?, ?)
            """, (draw_no, numbers_str, purchase_type, algorithm, datetime.now().isoformat()))

            record_id = cursor.lastrowid
            conn.commit()
            conn.close()

            print(f"✅ 구매 기록 추가 완료 (ID: {record_id})")
            print(f"   회차: {draw_no}")
            print(f"   번호: {numbers_str}")
            print(f"   타입: {purchase_type}")

            return record_id

        except Exception as e:
            print(f"❌ 구매 기록 추가 실패: {str(e)}")
            return None

    def check_winning_results(self):
        """구매한 번호들의 당첨 결과 확인"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 아직 결과 분석이 안된 구매 기록들
            cursor.execute("""
                SELECT pr.id, pr.draw_no, pr.numbers, pr.algorithm_used
                FROM purchase_records pr
                JOIN lotto_results lr ON pr.draw_no = lr.draw_no
                WHERE pr.result_analyzed = 0
            """)

            unchecked_records = cursor.fetchall()

            if not unchecked_records:
                print("📊 새로 확인할 구매 기록이 없습니다.")
                return 0

            print(f"🔍 {len(unchecked_records)}개 구매 기록 당첨 확인 중...")

            updated_count = 0

            for record_id, draw_no, numbers_str, algorithm in unchecked_records:
                # 구매한 번호들
                purchase_numbers = set(map(int, numbers_str.split(',')))

                # 해당 회차 당첨번호
                cursor.execute("""
                    SELECT num1, num2, num3, num4, num5, num6, bonus_num
                    FROM lotto_results WHERE draw_no = ?
                """, (draw_no,))

                result = cursor.fetchone()
                if not result:
                    continue

                winning_numbers = set(result[:6])
                bonus_number = result[6]

                # 일치하는 번호 개수
                matched_count = len(purchase_numbers & winning_numbers)
                has_bonus = bonus_number in purchase_numbers

                # 당첨 금액 계산 (대략적)
                prize_amount = self.calculate_prize(matched_count, has_bonus)

                # 결과 업데이트
                cursor.execute("""
                    UPDATE purchase_records
                    SET matched_count = ?, prize_amount = ?, result_analyzed = 1
                    WHERE id = ?
                """, (matched_count, prize_amount, record_id))

                updated_count += 1

                # 결과 출력
                if matched_count >= 3:
                    bonus_text = " + 보너스" if has_bonus else ""
                    print(f"🎉 {draw_no}회차: {matched_count}개 맞춤{bonus_text} - {prize_amount:,}원")

            conn.commit()
            conn.close()

            print(f"✅ {updated_count}개 기록 당첨 확인 완료")
            return updated_count

        except Exception as e:
            print(f"❌ 당첨 확인 실패: {str(e)}")
            return 0

    def calculate_prize(self, matched_count, has_bonus=False):
        """당첨 금액 계산 (대략적)"""
        if matched_count == 6:
            return 2000000000  # 1등: 약 20억
        elif matched_count == 5 and has_bonus:
            return 50000000    # 2등: 약 5천만
        elif matched_count == 5:
            return 1500000     # 3등: 약 150만
        elif matched_count == 4:
            return 50000       # 4등: 5만원
        elif matched_count == 3:
            return 5000        # 5등: 5천원
        else:
            return 0

    def analyze_algorithm_performance(self):
        """알고리즘별 성과 분석"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    algorithm_used,
                    COUNT(*) as total_count,
                    AVG(matched_count) as avg_matched,
                    MAX(matched_count) as best_matched,
                    SUM(prize_amount) as total_prize,
                    SUM(CASE WHEN matched_count >= 3 THEN 1 ELSE 0 END) as winning_count
                FROM purchase_records
                WHERE result_analyzed = 1 AND algorithm_used IS NOT NULL
                GROUP BY algorithm_used
                ORDER BY avg_matched DESC
            """)

            results = cursor.fetchall()

            if not results:
                print("📊 분석할 알고리즘 데이터가 없습니다.")
                return

            print(f"\n🏆 알고리즘 성과 순위:")
            print("=" * 70)
            print(f"{'순위':<4} {'알고리즘':<15} {'총구매':<6} {'평균맞춤':<8} {'최고맞춤':<8} {'당첨금액':<12} {'당첨율':<8}")
            print("=" * 70)

            for i, (algo, total, avg_match, best, total_prize, winning) in enumerate(results, 1):
                win_rate = (winning / total) * 100 if total > 0 else 0
                print(f"{i:<4} {algo:<15} {total:<6} {avg_match:>7.1f} {best:>8} {total_prize:>11,} {win_rate:>7.1f}%")

            conn.close()

        except Exception as e:
            print(f"❌ 성과 분석 실패: {str(e)}")

    def get_purchase_statistics(self):
        """구매 통계 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 전체 통계
            cursor.execute("""
                SELECT
                    COUNT(*) as total_purchases,
                    COUNT(*) * 1000 as total_spent,
                    SUM(prize_amount) as total_won,
                    COUNT(CASE WHEN matched_count = 6 THEN 1 END) as jackpot,
                    COUNT(CASE WHEN matched_count = 5 THEN 1 END) as second,
                    COUNT(CASE WHEN matched_count = 4 THEN 1 END) as third,
                    COUNT(CASE WHEN matched_count = 3 THEN 1 END) as fourth
                FROM purchase_records
                WHERE result_analyzed = 1
            """)

            stats = cursor.fetchone()

            if stats and stats[0] > 0:
                total_purchases, total_spent, total_won = stats[:3]
                jackpot, second, third, fourth = stats[3:]

                roi = ((total_won - total_spent) / max(1, total_spent)) * 100

                print(f"\n💰 전체 구매 통계:")
                print(f"   총 구매: {total_purchases:,}회 ({total_spent:,}원)")
                print(f"   총 당첨: {total_won:,}원")
                print(f"   수익률: {roi:+.2f}%")
                print(f"\n🎯 당첨 현황:")
                print(f"   1등 (6개): {jackpot}회")
                print(f"   2,3등 (5개): {second}회")
                print(f"   4등 (4개): {third}회")
                print(f"   5등 (3개): {fourth}회")

            # 최근 구매 내역
            cursor.execute("""
                SELECT draw_no, numbers, matched_count, prize_amount, algorithm_used
                FROM purchase_records
                WHERE result_analyzed = 1
                ORDER BY draw_no DESC LIMIT 10
            """)

            recent = cursor.fetchall()

            if recent:
                print(f"\n📋 최근 구매 내역 (10개):")
                for draw_no, numbers, matched, prize, algo in recent:
                    status = "🎉" if matched >= 3 else "  "
                    print(f"   {status} {draw_no}회차: {numbers} -> {matched}개 맞춤 ({prize:,}원) [{algo}]")

            conn.close()

        except Exception as e:
            print(f"❌ 통계 조회 실패: {str(e)}")

    def add_recommended_purchases(self):
        """추천 번호를 구매 기록으로 추가"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 최신 추천 번호들 가져오기
            cursor.execute("""
                SELECT numbers, algorithm, week_no
                FROM recommended_numbers
                ORDER BY created_at DESC LIMIT 4
            """)

            recommendations = cursor.fetchall()

            if not recommendations:
                print("❌ 추천 번호가 없습니다.")
                return 0

            added_count = 0

            for numbers_str, algorithm, week_no in recommendations:
                try:
                    numbers = [int(x.strip()) for x in numbers_str.split(',')]

                    # 이미 구매 기록이 있는지 확인
                    cursor.execute("""
                        SELECT id FROM purchase_records
                        WHERE draw_no = ? AND numbers = ? AND algorithm_used = ?
                    """, (week_no, numbers_str, algorithm))

                    if cursor.fetchone():
                        continue  # 이미 있으면 건너뛰기

                    # 구매 기록 추가
                    record_id = self.add_purchase_record(
                        numbers, week_no, algorithm, 'auto'
                    )

                    if record_id:
                        added_count += 1

                except:
                    continue

            conn.close()
            print(f"✅ {added_count}개 추천 번호를 구매 기록에 추가했습니다.")
            return added_count

        except Exception as e:
            print(f"❌ 추천 번호 추가 실패: {str(e)}")
            return 0

def main():
    print("🛒 로또 구매 관리 시스템")
    print("=" * 50)

    db_path = '/volume1/web/lotto/database/lotto.db'
    manager = LottoPurchaseManager(db_path)

    print("1️⃣ 당첨 결과 확인...")
    manager.check_winning_results()

    print("\n2️⃣ 추천 번호를 구매 기록에 추가...")
    manager.add_recommended_purchases()

    print("\n3️⃣ 알고리즘 성과 분석...")
    manager.analyze_algorithm_performance()

    print("\n4️⃣ 전체 구매 통계...")
    manager.get_purchase_statistics()

    print("\n🎉 구매 관리 완료!")

if __name__ == "__main__":
    main()
