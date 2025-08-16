#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import sqlite3
from datetime import datetime
import time
import json

class LottoCrawler:
    def __init__(self, db_path):
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.api_url = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="

    def get_latest_draw_number(self):
        """현재 예상 최신 회차 번호 계산"""
        # 로또 1회차: 2002년 12월 7일
        # 매주 토요일 추첨
        start_date = datetime(2002, 12, 7)
        current_date = datetime.now()
        weeks_passed = (current_date - start_date).days // 7
        return weeks_passed + 1

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
                    'total_sales': data.get('totSellamnt', 0)
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
                (draw_no, draw_date, num1, num2, num3, num4, num5, num6, bonus_num, total_sales)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['draw_no'], result['draw_date'],
                result['numbers'][0], result['numbers'][1], result['numbers'][2],
                result['numbers'][3], result['numbers'][4], result['numbers'][5],
                result['bonus_num'], result['total_sales']
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"❌ 데이터 저장 실패: {str(e)}")
            return False

    def get_existing_draw_numbers(self):
        """이미 저장된 회차 번호들 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT draw_no FROM lotto_results")
            existing = set(row[0] for row in cursor.fetchall())
            conn.close()
            return existing
        except:
            return set()

    def collect_recent_results(self, count=50):
        """최근 N회차 당첨번호 수집"""
        print(f"🎲 최근 {count}회차 당첨번호 수집 시작")

        # 현재 예상 최신 회차
        latest_draw = self.get_latest_draw_number()
        existing_draws = self.get_existing_draw_numbers()

        print(f"📊 예상 최신 회차: {latest_draw}")
        print(f"📋 기존 저장된 회차: {len(existing_draws)}개")

        collected = 0
        skipped = 0

        for i in range(count):
            draw_no = latest_draw - i

            if draw_no <= 0:
                break

            if draw_no in existing_draws:
                skipped += 1
                continue

            print(f"🔥 {draw_no}회차 수집 중...")
            result = self.get_lotto_result(draw_no)

            if result and self.save_lotto_result(result):
                collected += 1
                numbers_str = '-'.join([f'{n:2d}' for n in result['numbers']])
                print(f"   ✅ {numbers_str} + {result['bonus_num']:2d}")
            else:
                print(f"   ❌ 수집 실패")

            time.sleep(0.5)  # 서버 부하 방지

        print(f"\n🎉 수집 완료! 새로 추가: {collected}개, 건너뜀: {skipped}개")
        return collected

    def update_all_missing(self):
        """누락된 모든 회차 수집"""
        print("🔍 누락된 회차 검색 중...")

        latest_draw = self.get_latest_draw_number()
        existing_draws = self.get_existing_draw_numbers()

        missing_draws = []
        for draw_no in range(1, latest_draw + 1):
            if draw_no not in existing_draws:
                missing_draws.append(draw_no)

        if not missing_draws:
            print("✅ 누락된 회차가 없습니다!")
            return 0

        print(f"📋 누락된 회차: {len(missing_draws)}개")

        collected = 0
        for draw_no in missing_draws[:100]:  # 한 번에 최대 100개
            print(f"🔥 {draw_no}회차 수집 중...")
            result = self.get_lotto_result(draw_no)

            if result and self.save_lotto_result(result):
                collected += 1
                numbers_str = '-'.join([f'{n:2d}' for n in result['numbers']])
                print(f"   ✅ {numbers_str} + {result['bonus_num']:2d}")
            else:
                print(f"   ❌ 수집 실패")

            time.sleep(0.5)

        print(f"\n🎉 누락 회차 수집 완료: {collected}개")
        return collected

def main():
    print("🕷️ 로또 데이터 수집기")
    print("=" * 50)

    db_path = '/volume1/web/lotto/database/lotto.db'
    crawler = LottoCrawler(db_path)

    # 최근 50회차 수집
    crawler.collect_recent_results(50)

    # 누락된 회차가 있다면 추가 수집
    print("\n" + "=" * 50)
    crawler.update_all_missing()

if __name__ == "__main__":
    main()
