#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import sqlite3
from datetime import datetime
import time
import json

class LottoFullCollector:
    def __init__(self, db_path):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.api_url = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="
    
    def get_lotto_result(self, draw_no):
        """특정 회차의 당첨번호 가져오기"""
        try:
            url = self.api_url + str(draw_no)
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if 'returnValue' in data and data['returnValue'] == 'success':
                result = {
                    'draw_no': draw_no,
                    'draw_date': data.get('drwNoDate', ''),
                    'numbers': [
                        data.get('drwtNo1', 0),
                        data.get('drwtNo2', 0),
                        data.get('drwtNo3', 0),
                        data.get('drwtNo4', 0),
                        data.get('drwtNo5', 0),
                        data.get('drwtNo6', 0)
                    ],
                    'bonus_num': data.get('bnusNo', 0),
                    'total_sales': data.get('totSellamnt', 0),
                    'winner_1st': data.get('firstWinamnt', 0),
                    'prize_1st': data.get('firstPrzwnerCo', 0)
                }
                
                # 데이터 유효성 검사
                if all(1 <= num <= 45 for num in result['numbers']) and 1 <= result['bonus_num'] <= 45:
                    return result
            
            return None
            
        except Exception as e:
            print(f"❌ {draw_no}회차 수집 실패: {str(e)}")
            return None
    
    def save_lotto_result(self, result):
        """당첨번호를 데이터베이스에 저장"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO lotto_results 
                (draw_no, draw_date, num1, num2, num3, num4, num5, num6, bonus_num, 
                 total_sales, winner_1st, prize_1st)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['draw_no'], result['draw_date'],
                result['numbers'][0], result['numbers'][1], result['numbers'][2],
                result['numbers'][3], result['numbers'][4], result['numbers'][5],
                result['bonus_num'], result['total_sales'],
                result['winner_1st'], result['prize_1st']
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ 데이터 저장 실패: {str(e)}")
            return False
    
    def get_existing_draws(self):
        """이미 저장된 회차들 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT draw_no FROM lotto_results ORDER BY draw_no")
            existing = set(row[0] for row in cursor.fetchall())
            conn.close()
            return existing
        except:
            return set()
    
    def get_latest_draw_number(self):
        """최신 회차 번호 계산"""
        start_date = datetime(2002, 12, 7)
        current_date = datetime.now()
        weeks_passed = (current_date - start_date).days // 7
        return weeks_passed + 1
    
    def collect_all_missing_draws(self):
        """누락된 모든 회차 수집"""
        print("🏁 전체 로또 데이터 수집 시작")
        print("=" * 60)
        
        latest_draw = self.get_latest_draw_number()
        existing_draws = self.get_existing_draws()
        
        print(f"📊 예상 최신 회차: {latest_draw}")
        print(f"📋 기존 저장된 회차: {len(existing_draws)}개")
        
        # 누락된 회차 찾기
        all_draws = set(range(1, latest_draw + 1))
        missing_draws = sorted(all_draws - existing_draws)
        
        if not missing_draws:
            print("✅ 모든 회차가 이미 저장되어 있습니다!")
            return 0
        
        print(f"🔍 누락된 회차: {len(missing_draws)}개")
        print(f"📝 수집 범위: {min(missing_draws)}회차 ~ {max(missing_draws)}회차")
        
        collected = 0
        failed = 0
        total_missing = len(missing_draws)
        
        for i, draw_no in enumerate(missing_draws, 1):
            print(f"🔥 [{i}/{total_missing}] {draw_no}회차 수집 중... ", end="")
            
            result = self.get_lotto_result(draw_no)
            
            if result and self.save_lotto_result(result):
                collected += 1
                numbers_str = '-'.join([f'{n:2d}' for n in result['numbers']])
                print(f"✅ {numbers_str} + {result['bonus_num']:2d}")
            else:
                failed += 1
                print(f"❌ 실패")
            
            # 진행률 표시
            if i % 10 == 0:
                progress = (i / total_missing) * 100
                print(f"📈 진행률: {progress:.1f}% (성공: {collected}, 실패: {failed})")
            
            time.sleep(0.3)  # 서버 부하 방지
        
        print("\n" + "=" * 60)
        print(f"🎉 전체 데이터 수집 완료!")
        print(f"✅ 성공: {collected}개")
        print(f"❌ 실패: {failed}개")
        print(f"📊 총 저장된 회차: {len(self.get_existing_draws())}개")
        
        return collected
    
    def weekly_update(self):
        """주간 업데이트 (최신 회차만)"""
        print("📅 주간 업데이트 실행")
        
        latest_draw = self.get_latest_draw_number()
        existing_draws = self.get_existing_draws()
        
        # 최근 5회차 확인
        new_draws = []
        for i in range(5):
            draw_no = latest_draw - i
            if draw_no > 0 and draw_no not in existing_draws:
                new_draws.append(draw_no)
        
        if not new_draws:
            print("✅ 새로운 당첨번호가 없습니다.")
            return 0
        
        collected = 0
        for draw_no in sorted(new_draws):
            print(f"🆕 {draw_no}회차 수집 중...")
            result = self.get_lotto_result(draw_no)
            
            if result and self.save_lotto_result(result):
                collected += 1
                numbers_str = '-'.join([f'{n:2d}' for n in result['numbers']])
                print(f"   ✅ {numbers_str} + {result['bonus_num']:2d}")
            
            time.sleep(0.5)
        
        print(f"🎉 주간 업데이트 완료: {collected}개 추가")
        return collected

def main():
    print("🎲 로또 전체 데이터 수집기")
    print("=" * 50)
    
    db_path = '/volume1/web/lotto/database/lotto.db'
    collector = LottoFullCollector(db_path)
    
    print("다음 중 선택하세요:")
    print("1. 전체 누락 회차 수집 (시간 소요)")
    print("2. 주간 업데이트만")
    
    try:
        choice = input("선택 (1 또는 2): ").strip()
        
        if choice == "1":
            collector.collect_all_missing_draws()
        elif choice == "2":
            collector.weekly_update()
        else:
            print("❌ 잘못된 선택입니다.")
    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단되었습니다.")
    except:
        # 인터랙티브 모드가 아닐 때는 전체 수집 실행
        collector.collect_all_missing_draws()

if __name__ == "__main__":
    main()
