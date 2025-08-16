#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime
from collections import defaultdict

class DetailedVerifier:
    def __init__(self, db_path):
        self.db_path = db_path
    
    def get_all_data(self):
        """전체 데이터를 메모리로 가져와서 정확하게 계산"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 모든 당첨 결과 가져오기
            cursor.execute("""
                SELECT draw_no, draw_date, num1, num2, num3, num4, num5, num6, bonus_num
                FROM lotto_results 
                ORDER BY draw_no ASC
            """)
            
            all_results = cursor.fetchall()
            conn.close()
            
            print(f"📊 총 {len(all_results)}회차 데이터 로드")
            print(f"📅 범위: {all_results[0][0]}회차 ~ {all_results[-1][0]}회차")
            
            return all_results
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {str(e)}")
            return []
    
    def manual_calculation(self, all_results):
        """수동으로 각 번호의 최근 출현 계산"""
        if not all_results:
            return {}
        
        latest_draw = all_results[-1][0]  # 최신 회차
        
        # 각 번호별 최근 출현 추적
        last_appearance = {}  # {번호: (회차, 타입)}
        frequency = defaultdict(int)
        bonus_frequency = defaultdict(int)
        
        print(f"\n🔍 수동 계산 중... (최신 회차: {latest_draw})")
        
        for draw_no, draw_date, n1, n2, n3, n4, n5, n6, bonus in all_results:
            # 일반 번호 처리
            normal_numbers = [n1, n2, n3, n4, n5, n6]
            for num in normal_numbers:
                last_appearance[num] = (draw_no, 'normal')
                frequency[num] += 1
            
            # 보너스 번호 처리
            last_appearance[bonus] = (draw_no, 'bonus')
            bonus_frequency[bonus] += 1
        
        # 미출현 주차 계산
        overdue_data = {}
        
        for num in range(1, 46):
            if num in last_appearance:
                last_draw, appear_type = last_appearance[num]
                not_drawn_weeks = latest_draw - last_draw
                overdue_data[num] = {
                    'last_draw': last_draw,
                    'not_drawn_weeks': not_drawn_weeks,
                    'appear_type': appear_type,
                    'frequency': frequency[num],
                    'bonus_frequency': bonus_frequency[num]
                }
            else:
                # 한 번도 나오지 않은 번호 (이론적으로 불가능)
                overdue_data[num] = {
                    'last_draw': 0,
                    'not_drawn_weeks': latest_draw,
                    'appear_type': 'never',
                    'frequency': 0,
                    'bonus_frequency': 0
                }
        
        return overdue_data, latest_draw
    
    def compare_with_database(self, manual_data, latest_draw):
        """수동 계산과 DB 데이터 비교"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT number, frequency, not_drawn_weeks, last_drawn, bonus_frequency
                FROM number_frequency
                ORDER BY number
            """)
            
            db_data = cursor.fetchall()
            conn.close()
            
            print(f"\n📋 DB vs 수동계산 비교 (최신 회차: {latest_draw})")
            print("=" * 80)
            print(f"{'번호':<4} {'DB미출현':<8} {'실제미출현':<8} {'DB마지막':<8} {'실제마지막':<10} {'타입':<8} {'상태':<8}")
            print("=" * 80)
            
            discrepancies = []
            
            for row in db_data:
                num, db_freq, db_not_drawn, db_last_drawn, db_bonus_freq = row
                
                manual_info = manual_data.get(num, {})
                real_not_drawn = manual_info.get('not_drawn_weeks', 0)
                real_last_draw = manual_info.get('last_draw', 0)
                appear_type = manual_info.get('appear_type', 'unknown')
                
                # 문제 있는 경우 표시
                if db_not_drawn != real_not_drawn or str(db_last_drawn) != str(real_last_draw):
                    status = "❌ 불일치"
                    discrepancies.append((num, db_not_drawn, real_not_drawn, db_last_drawn, real_last_draw))
                else:
                    status = "✅ 일치"
                
                print(f"{num:<4} {db_not_drawn:<8} {real_not_drawn:<8} {db_last_drawn:<8} {real_last_draw:<10} {appear_type:<8} {status:<8}")
            
            if discrepancies:
                print(f"\n⚠️ 총 {len(discrepancies)}개 번호에서 불일치 발견!")
                
                print(f"\n🔥 미출현 상위 번호 (수동 계산 기준):")
                sorted_overdue = sorted(manual_data.items(), key=lambda x: x[1]['not_drawn_weeks'], reverse=True)
                for i, (num, data) in enumerate(sorted_overdue[:10], 1):
                    print(f"{i:2d}. {num:2d}번: {data['not_drawn_weeks']}주차 전 ({data['last_draw']}회차, {data['appear_type']})")
            else:
                print(f"\n✅ 모든 번호가 일치합니다!")
            
            return discrepancies
            
        except Exception as e:
            print(f"❌ DB 비교 실패: {str(e)}")
            return []
    
    def fix_database(self, manual_data, latest_draw):
        """DB 데이터 수정"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print(f"\n🔧 데이터베이스 수정 중...")
            
            updated_count = 0
            
            for num in range(1, 46):
                manual_info = manual_data.get(num, {})
                
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
                    manual_info.get('frequency', 0),
                    manual_info.get('not_drawn_weeks', 0),
                    str(manual_info.get('last_draw', '')),
                    manual_info.get('bonus_frequency', 0),
                    datetime.now().isoformat(),
                    num
                ))
                
                updated_count += 1
            
            conn.commit()
            conn.close()
            
            print(f"✅ {updated_count}개 번호 데이터 수정 완료")
            return True
            
        except Exception as e:
            print(f"❌ DB 수정 실패: {str(e)}")
            return False
    
    def verify_specific_numbers(self, all_results, numbers_to_check):
        """특정 번호들 상세 검증"""
        print(f"\n🔍 특정 번호들 상세 검증:")
        print("=" * 60)
        
        latest_draw = all_results[-1][0] if all_results else 0
        
        for check_num in numbers_to_check:
            print(f"\n📌 {check_num}번 상세 검증:")
            
            appearances = []
            
            # 모든 출현 기록 찾기
            for draw_no, draw_date, n1, n2, n3, n4, n5, n6, bonus in all_results:
                if check_num in [n1, n2, n3, n4, n5, n6]:
                    appearances.append((draw_no, draw_date, 'normal', [n1, n2, n3, n4, n5, n6]))
                elif check_num == bonus:
                    appearances.append((draw_no, draw_date, 'bonus', bonus))
            
            if appearances:
                # 최근 출현
                latest_appearance = max(appearances, key=lambda x: x[0])
                not_drawn = latest_draw - latest_appearance[0]
                
                print(f"   총 출현: {len(appearances)}회")
                print(f"   최근 출현: {latest_appearance[0]}회차 ({latest_appearance[1]}) - {latest_appearance[2]}")
                print(f"   미출현: {not_drawn}주차")
                
                # 최근 5회 출현
                recent_5 = sorted(appearances, key=lambda x: x[0], reverse=True)[:5]
                print(f"   최근 5회 출현:")
                for i, (draw, date, type_str, data) in enumerate(recent_5, 1):
                    if type_str == 'normal':
                        print(f"     {i}. {draw}회차 ({date}) - 일반: {data}")
                    else:
                        print(f"     {i}. {draw}회차 ({date}) - 보너스: {data}")
            else:
                print(f"   ❌ 출현 기록이 없습니다!")

def main():
    print("🔍 로또 미출현 번호 정밀 검증 시스템")
    print("=" * 60)
    
    db_path = '/volume1/web/lotto/database/lotto.db'
    verifier = DetailedVerifier(db_path)
    
    # 1. 전체 데이터 로드
    print("1️⃣ 전체 데이터 로드...")
    all_results = verifier.get_all_data()
    
    if not all_results:
        print("❌ 데이터 로드 실패")
        return
    
    # 2. 수동 계산
    print("\n2️⃣ 수동 계산 수행...")
    manual_data, latest_draw = verifier.manual_calculation(all_results)
    
    # 3. DB와 비교
    print("\n3️⃣ DB 데이터와 비교...")
    discrepancies = verifier.compare_with_database(manual_data, latest_draw)
    
    # 4. 특정 번호들 상세 검증
    print("\n4️⃣ 문제 번호들 상세 검증...")
    problem_numbers = [10, 23, 29, 33, 37]  # 이전에 문제가 있었던 번호들
    verifier.verify_specific_numbers(all_results, problem_numbers)
    
    # 5. DB 수정
    if discrepancies:
        print("\n5️⃣ 데이터베이스 수정...")
        verifier.fix_database(manual_data, latest_draw)
        
        print("\n6️⃣ 수정 후 재검증...")
        verifier.compare_with_database(manual_data, latest_draw)
    
    print("\n🎉 정밀 검증 완료!")

if __name__ == "__main__":
    main()
