#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime

class OverdueVerifier:
    def __init__(self, db_path):
        self.db_path = db_path
    
    def verify_specific_number(self, target_number):
        """특정 번호의 출현 이력 검증"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n🔍 {target_number}번 검증 중...")
            print("=" * 50)
            
            # 해당 번호가 포함된 모든 회차 조회 (최신순)
            cursor.execute("""
                SELECT draw_no, draw_date, num1, num2, num3, num4, num5, num6, bonus_num
                FROM lotto_results 
                WHERE num1 = ? OR num2 = ? OR num3 = ? OR num4 = ? OR num5 = ? OR num6 = ?
                ORDER BY draw_no DESC
            """, (target_number,) * 6)
            
            appearances = cursor.fetchall()
            
            # 보너스 번호로 출현한 경우도 조회
            cursor.execute("""
                SELECT draw_no, draw_date, num1, num2, num3, num4, num5, num6, bonus_num
                FROM lotto_results 
                WHERE bonus_num = ?
                ORDER BY draw_no DESC
            """, (target_number,))
            
            bonus_appearances = cursor.fetchall()
            
            # 최신 회차 조회
            cursor.execute("SELECT MAX(draw_no) FROM lotto_results")
            latest_draw = cursor.fetchone()[0]
            
            # number_frequency 테이블의 정보
            cursor.execute("""
                SELECT frequency, not_drawn_weeks, last_drawn, bonus_frequency
                FROM number_frequency WHERE number = ?
            """, (target_number,))
            
            freq_data = cursor.fetchone()
            
            conn.close()
            
            print(f"📊 현재 데이터베이스 정보:")
            if freq_data:
                frequency, not_drawn_weeks, last_drawn, bonus_frequency = freq_data
                print(f"   일반 출현: {frequency}회")
                print(f"   보너스 출현: {bonus_frequency}회")
                print(f"   미출현 주차: {not_drawn_weeks}주차")
                print(f"   마지막 출현: {last_drawn}회차")
            
            print(f"\n📋 실제 출현 이력 (일반번호):")
            if appearances:
                print(f"   총 출현 횟수: {len(appearances)}회")
                print(f"   최근 출현 TOP 10:")
                for i, (draw_no, draw_date, n1, n2, n3, n4, n5, n6, bonus) in enumerate(appearances[:10], 1):
                    numbers = [n1, n2, n3, n4, n5, n6]
                    print(f"   {i:2d}. {draw_no:4d}회차 ({draw_date}) - {numbers}")
                
                last_appearance = appearances[0][0]  # 가장 최근 출현
                calculated_weeks = latest_draw - last_appearance
                print(f"\n   최근 출현: {last_appearance}회차")
                print(f"   최신 회차: {latest_draw}회차")
                print(f"   계산된 미출현: {calculated_weeks}주차")
            else:
                print(f"   일반번호로 출현한 기록이 없습니다!")
            
            print(f"\n🎁 보너스 번호 출현 이력:")
            if bonus_appearances:
                print(f"   보너스 출현 횟수: {len(bonus_appearances)}회")
                print(f"   보너스 출현 TOP 5:")
                for i, (draw_no, draw_date, n1, n2, n3, n4, n5, n6, bonus) in enumerate(bonus_appearances[:5], 1):
                    print(f"   {i:2d}. {draw_no:4d}회차 ({draw_date}) - 보너스: {bonus}")
            else:
                print(f"   보너스 번호로 출현한 기록이 없습니다!")
            
            # 전체 출현 (일반 + 보너스)
            all_appearances = []
            for row in appearances:
                all_appearances.append((row[0], row[1], 'normal'))
            for row in bonus_appearances:
                all_appearances.append((row[0], row[1], 'bonus'))
            
            all_appearances.sort(key=lambda x: x[0], reverse=True)
            
            print(f"\n🔄 전체 출현 이력 (일반 + 보너스):")
            print(f"   총 출현: {len(all_appearances)}회")
            if all_appearances:
                most_recent = all_appearances[0]
                print(f"   가장 최근: {most_recent[0]}회차 ({most_recent[1]}) - {most_recent[2]}")
                real_weeks = latest_draw - most_recent[0]
                print(f"   실제 미출현: {real_weeks}주차")
            
            # 검증 결과
            print(f"\n✅ 검증 결과:")
            if freq_data and all_appearances:
                db_weeks = freq_data[1]  # not_drawn_weeks
                real_weeks = latest_draw - all_appearances[0][0]
                if db_weeks == real_weeks:
                    print(f"   ✅ 미출현 계산 정확함: {db_weeks}주차")
                else:
                    print(f"   ❌ 미출현 계산 오류!")
                    print(f"      DB: {db_weeks}주차")
                    print(f"      실제: {real_weeks}주차")
            
            return True
            
        except Exception as e:
            print(f"❌ 검증 실패: {str(e)}")
            return False
    
    def verify_top_overdue_numbers(self):
        """상위 미출현 번호들 검증"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 상위 미출현 번호 10개
            cursor.execute("""
                SELECT number, not_drawn_weeks, last_drawn
                FROM number_frequency
                ORDER BY not_drawn_weeks DESC LIMIT 10
            """)
            
            overdue_numbers = cursor.fetchall()
            conn.close()
            
            print(f"\n🏆 상위 미출현 번호 10개 검증:")
            print("=" * 60)
            
            for i, (number, weeks, last_drawn) in enumerate(overdue_numbers, 1):
                print(f"\n{i:2d}. {number:2d}번 - {weeks}주차 전 (마지막: {last_drawn}회차)")
                self.verify_specific_number(number)
                print("-" * 30)
            
            return True
            
        except Exception as e:
            print(f"❌ 상위 미출현 번호 검증 실패: {str(e)}")
            return False
    
    def fix_overdue_calculation(self):
        """미출현 계산 수정"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n🔧 미출현 계산 수정 중...")
            
            # 최신 회차
            cursor.execute("SELECT MAX(draw_no) FROM lotto_results")
            latest_draw = cursor.fetchone()[0]
            
            print(f"📊 최신 회차: {latest_draw}")
            
            fixed_count = 0
            
            for num in range(1, 46):
                # 해당 번호의 가장 최근 출현 찾기 (일반번호 + 보너스)
                cursor.execute("""
                    SELECT MAX(draw_no) FROM lotto_results 
                    WHERE num1 = ? OR num2 = ? OR num3 = ? OR num4 = ? OR num5 = ? OR num6 = ? OR bonus_num = ?
                """, (num,) * 7)
                
                last_appearance = cursor.fetchone()[0]
                
                if last_appearance:
                    not_drawn_weeks = latest_draw - last_appearance
                    
                    # 업데이트
                    cursor.execute("""
                        UPDATE number_frequency 
                        SET not_drawn_weeks = ?, last_drawn = ?, updated_at = ?
                        WHERE number = ?
                    """, (not_drawn_weeks, str(last_appearance), datetime.now().isoformat(), num))
                    
                    fixed_count += 1
                else:
                    # 한 번도 나오지 않은 번호
                    cursor.execute("""
                        UPDATE number_frequency 
                        SET not_drawn_weeks = ?, last_drawn = '', updated_at = ?
                        WHERE number = ?
                    """, (latest_draw, datetime.now().isoformat(), num))
            
            conn.commit()
            conn.close()
            
            print(f"✅ {fixed_count}개 번호 미출현 계산 수정 완료")
            return True
            
        except Exception as e:
            print(f"❌ 미출현 계산 수정 실패: {str(e)}")
            return False

def main():
    print("🔍 로또 미출현 번호 검증 시스템")
    print("=" * 50)
    
    db_path = '/volume1/web/lotto/database/lotto.db'
    verifier = OverdueVerifier(db_path)
    
    # 10번 상세 검증
    print("1️⃣ 10번 상세 검증...")
    verifier.verify_specific_number(10)
    
    # 상위 미출현 번호들 검증
    print("\n2️⃣ 상위 미출현 번호들 검증...")
    verifier.verify_top_overdue_numbers()
    
    # 미출현 계산 수정
    print("\n3️⃣ 미출현 계산 수정...")
    verifier.fix_overdue_calculation()
    
    print("\n🎉 미출현 번호 검증 완료!")

if __name__ == "__main__":
    main()
