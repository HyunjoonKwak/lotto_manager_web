#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime

class DBDeepInspection:
    def __init__(self, db_path):
        self.db_path = db_path

    def inspect_database_structure(self):
        """데이터베이스 구조 검사"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("🔍 데이터베이스 구조 검사")
            print("=" * 50)

            # 테이블 목록
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"📋 테이블 목록: {[t[0] for t in tables]}")

            # lotto_results 테이블 정보
            cursor.execute("PRAGMA table_info(lotto_results)")
            columns = cursor.fetchall()
            print(f"\n📊 lotto_results 컬럼:")
            for col in columns:
                print(f"   {col[1]} ({col[2]})")

            # number_frequency 테이블 정보
            cursor.execute("PRAGMA table_info(number_frequency)")
            freq_columns = cursor.fetchall()
            print(f"\n📈 number_frequency 컬럼:")
            for col in freq_columns:
                print(f"   {col[1]} ({col[2]})")

            conn.close()
            return True

        except Exception as e:
            print(f"❌ DB 구조 검사 실패: {str(e)}")
            return False

    def check_raw_data_integrity(self):
        """원본 데이터 무결성 검사"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\n🔍 원본 데이터 무결성 검사")
            print("=" * 50)

            # 전체 회차 수
            cursor.execute("SELECT COUNT(*) FROM lotto_results")
            total_count = cursor.fetchone()[0]
            print(f"📊 총 회차 수: {total_count}")

            # 회차 범위
            cursor.execute("SELECT MIN(draw_no), MAX(draw_no) FROM lotto_results")
            min_draw, max_draw = cursor.fetchone()
            print(f"📅 회차 범위: {min_draw} ~ {max_draw}")

            # 누락된 회차 확인
            cursor.execute("SELECT draw_no FROM lotto_results ORDER BY draw_no")
            all_draws = [row[0] for row in cursor.fetchall()]

            missing_draws = []
            for i in range(min_draw, max_draw + 1):
                if i not in all_draws:
                    missing_draws.append(i)

            if missing_draws:
                print(f"⚠️ 누락된 회차: {missing_draws[:10]}{'...' if len(missing_draws) > 10 else ''} (총 {len(missing_draws)}개)")
            else:
                print("✅ 회차 연속성: 누락 없음")

            # 데이터 유효성 검사 (번호 범위)
            cursor.execute("""
                SELECT draw_no, num1, num2, num3, num4, num5, num6, bonus_num
                FROM lotto_results
                WHERE num1 < 1 OR num1 > 45 OR num2 < 1 OR num2 > 45
                   OR num3 < 1 OR num3 > 45 OR num4 < 1 OR num4 > 45
                   OR num5 < 1 OR num5 > 45 OR num6 < 1 OR num6 > 45
                   OR bonus_num < 1 OR bonus_num > 45
                LIMIT 10
            """)

            invalid_data = cursor.fetchall()
            if invalid_data:
                print(f"❌ 잘못된 번호 범위 데이터: {len(invalid_data)}개")
                for row in invalid_data:
                    print(f"   {row}")
            else:
                print("✅ 번호 범위: 모두 1-45 범위 내")

            # 최신 데이터 확인
            cursor.execute("""
                SELECT draw_no, draw_date, num1, num2, num3, num4, num5, num6, bonus_num
                FROM lotto_results
                ORDER BY draw_no DESC LIMIT 5
            """)

            recent_data = cursor.fetchall()
            print(f"\n📋 최신 5회차 데이터:")
            for row in recent_data:
                draw_no, draw_date, n1, n2, n3, n4, n5, n6, bonus = row
                print(f"   {draw_no}회차 ({draw_date}): {n1}-{n2}-{n3}-{n4}-{n5}-{n6} + {bonus}")

            conn.close()
            return True, max_draw

        except Exception as e:
            print(f"❌ 데이터 무결성 검사 실패: {str(e)}")
            return False, 0

    def analyze_number_frequency_table(self):
        """number_frequency 테이블 분석"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\n🔍 number_frequency 테이블 분석")
            print("=" * 50)

            # 전체 번호 확인
            cursor.execute("SELECT COUNT(*) FROM number_frequency")
            count = cursor.fetchone()[0]
            print(f"📊 저장된 번호 개수: {count}/45")

            # 누락된 번호 확인
            cursor.execute("SELECT number FROM number_frequency ORDER BY number")
            existing_numbers = [row[0] for row in cursor.fetchall()]
            missing_numbers = [i for i in range(1, 46) if i not in existing_numbers]

            if missing_numbers:
                print(f"❌ 누락된 번호: {missing_numbers}")
            else:
                print("✅ 번호 완성도: 1-45 모두 존재")

            # 이상한 값들 확인
            cursor.execute("""
                SELECT number, frequency, not_drawn_weeks, last_drawn, bonus_frequency
                FROM number_frequency
                ORDER BY not_drawn_weeks DESC LIMIT 10
            """)

            top_overdue = cursor.fetchall()
            print(f"\n📋 미출현 상위 10개 (DB 기준):")
            for row in top_overdue:
                num, freq, not_drawn, last_drawn, bonus_freq = row
                print(f"   {num:2d}번: {not_drawn:4d}주차 전 (마지막: {last_drawn}, 빈도: {freq})")

            # 음수나 비정상적인 값 확인
            cursor.execute("""
                SELECT number, frequency, not_drawn_weeks, last_drawn
                FROM number_frequency
                WHERE frequency < 0 OR not_drawn_weeks < 0
            """)

            abnormal_data = cursor.fetchall()
            if abnormal_data:
                print(f"❌ 비정상적인 값들:")
                for row in abnormal_data:
                    print(f"   {row}")

            conn.close()
            return True

        except Exception as e:
            print(f"❌ frequency 테이블 분석 실패: {str(e)}")
            return False

    def manual_recalculate_overdue(self):
        """완전히 새로운 미출현 계산"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\n🔧 완전 새로운 미출현 계산 시작")
            print("=" * 50)

            # 최신 회차 확인
            cursor.execute("SELECT MAX(draw_no) FROM lotto_results")
            latest_draw = cursor.fetchone()[0]
            print(f"📊 최신 회차: {latest_draw}")

            # 각 번호별로 직접 계산
            overdue_results = {}

            for num in range(1, 46):
                print(f"🔍 {num}번 계산 중...", end=" ")

                # 일반 번호로 최근 출현
                cursor.execute("""
                    SELECT MAX(draw_no) FROM lotto_results
                    WHERE num1 = ? OR num2 = ? OR num3 = ? OR num4 = ? OR num5 = ? OR num6 = ?
                """, (num, num, num, num, num, num))

                last_normal = cursor.fetchone()[0]

                # 보너스 번호로 최근 출현
                cursor.execute("""
                    SELECT MAX(draw_no) FROM lotto_results WHERE bonus_num = ?
                """, (num,))

                last_bonus = cursor.fetchone()[0]

                # 전체 출현 횟수 (일반)
                cursor.execute("""
                    SELECT COUNT(*) FROM lotto_results
                    WHERE num1 = ? OR num2 = ? OR num3 = ? OR num4 = ? OR num5 = ? OR num6 = ?
                """, (num, num, num, num, num, num))

                normal_freq = cursor.fetchone()[0]

                # 보너스 출현 횟수
                cursor.execute("""
                    SELECT COUNT(*) FROM lotto_results WHERE bonus_num = ?
                """, (num,))

                bonus_freq = cursor.fetchone()[0]

                # 가장 최근 출현 계산
                last_appearance = None
                appear_type = None

                if last_normal and last_bonus:
                    if last_normal >= last_bonus:
                        last_appearance = last_normal
                        appear_type = 'normal'
                    else:
                        last_appearance = last_bonus
                        appear_type = 'bonus'
                elif last_normal:
                    last_appearance = last_normal
                    appear_type = 'normal'
                elif last_bonus:
                    last_appearance = last_bonus
                    appear_type = 'bonus'
                else:
                    last_appearance = 0
                    appear_type = 'never'

                # 미출현 주차 계산
                if last_appearance:
                    not_drawn_weeks = latest_draw - last_appearance
                else:
                    not_drawn_weeks = latest_draw

                overdue_results[num] = {
                    'last_appearance': last_appearance,
                    'not_drawn_weeks': not_drawn_weeks,
                    'appear_type': appear_type,
                    'normal_freq': normal_freq,
                    'bonus_freq': bonus_freq
                }

                print(f"최근: {last_appearance}회차({appear_type}), 미출현: {not_drawn_weeks}주차")

            # 결과 출력
            print(f"\n📋 새로 계산된 미출현 상위 10개:")
            sorted_overdue = sorted(overdue_results.items(), key=lambda x: x[1]['not_drawn_weeks'], reverse=True)

            for i, (num, data) in enumerate(sorted_overdue[:10], 1):
                print(f"{i:2d}. {num:2d}번: {data['not_drawn_weeks']:2d}주차 전 ({data['last_appearance']}회차, {data['appear_type']})")

            # DB 업데이트
            print(f"\n🔧 데이터베이스 업데이트 중...")
            for num, data in overdue_results.items():
                cursor.execute("""
                    UPDATE number_frequency
                    SET
                        frequency = ?,
                        not_drawn_weeks = ?,
                        last_drawn = ?,
                        bonus_frequency = ?,
                        updated_at = ?
                    WHERE number = ?
                """, (
                    data['normal_freq'],
                    data['not_drawn_weeks'],
                    str(data['last_appearance']) if data['last_appearance'] else '',
                    data['bonus_freq'],
                    datetime.now().isoformat(),
                    num
                ))

            conn.commit()
            conn.close()

            print(f"✅ 모든 번호 업데이트 완료")
            return overdue_results

        except Exception as e:
            print(f"❌ 미출현 재계산 실패: {str(e)}")
            return {}

def main():
    print("🔍 데이터베이스 완전 검증 및 재계산")
    print("=" * 60)

    db_path = '/volume1/web/lotto/database/lotto.db'
    inspector = DBDeepInspection(db_path)

    # 1. DB 구조 검사
    print("1️⃣ 데이터베이스 구조 검사...")
    inspector.inspect_database_structure()

    # 2. 원본 데이터 무결성 검사
    print("\n2️⃣ 원본 데이터 무결성 검사...")
    data_ok, max_draw = inspector.check_raw_data_integrity()

    if not data_ok:
        print("❌ 원본 데이터에 문제가 있습니다. 먼저 데이터를 수정해주세요.")
        return

    # 3. number_frequency 테이블 분석
    print("\n3️⃣ number_frequency 테이블 분석...")
    inspector.analyze_number_frequency_table()

    # 4. 완전 새로운 계산
    print("\n4️⃣ 완전 새로운 미출현 계산...")
    new_results = inspector.manual_recalculate_overdue()

    if new_results:
        print("\n🎉 데이터베이스 완전 검증 및 재계산 완료!")
    else:
        print("\n❌ 재계산 실패")

if __name__ == "__main__":
    main()
