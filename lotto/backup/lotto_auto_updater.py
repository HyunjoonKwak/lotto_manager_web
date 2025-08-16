#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import subprocess
import os
from datetime import datetime
import time

class LottoAutoUpdater:
    def __init__(self, scripts_path):
        self.scripts_path = scripts_path
        self.db_path = '/volume1/web/lotto/database/lotto.db'
    
    def log_message(self, message):
        """로그 메시지 출력"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
    
    def run_script(self, script_name, timeout=300):
        """스크립트 실행"""
        try:
            script_path = os.path.join(self.scripts_path, script_name)
            
            if not os.path.exists(script_path):
                self.log_message(f"❌ 스크립트 없음: {script_name}")
                return False
            
            self.log_message(f"🔄 실행 중: {script_name}")
            
            result = subprocess.run(
                ['python3', script_path], 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                cwd=self.scripts_path
            )
            
            if result.returncode == 0:
                self.log_message(f"✅ 완료: {script_name}")
                return True
            else:
                self.log_message(f"❌ 실패: {script_name}")
                if result.stderr:
                    self.log_message(f"   오류: {result.stderr[:200]}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_message(f"⏰ 시간 초과: {script_name}")
            return False
        except Exception as e:
            self.log_message(f"❌ 예외 발생: {script_name} - {str(e)}")
            return False
    
    def check_new_draw(self):
        """새로운 회차가 있는지 확인"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 최신 저장된 회차
            cursor.execute("SELECT MAX(draw_no) FROM lotto_results")
            latest_saved = cursor.fetchone()[0] or 0
            
            # 예상 최신 회차
            start_date = datetime(2002, 12, 7)
            current_date = datetime.now()
            weeks_passed = (current_date - start_date).days // 7
            expected_latest = weeks_passed + 1
            
            conn.close()
            
            if expected_latest > latest_saved:
                self.log_message(f"🆕 새로운 회차 발견: {expected_latest} (저장된 최신: {latest_saved})")
                return True
            else:
                self.log_message(f"📊 최신 상태: {latest_saved}회차")
                return False
                
        except Exception as e:
            self.log_message(f"❌ 회차 확인 실패: {str(e)}")
            return False
    
    def full_update_cycle(self):
        """전체 업데이트 사이클 실행"""
        self.log_message("🚀 로또 자동 업데이트 시작")
        self.log_message("=" * 50)
        
        success_count = 0
        total_steps = 5
        
        # 1. 새로운 당첨번호 수집
        if self.run_script('lotto_crawler.py', 180):
            success_count += 1
        
        time.sleep(2)
        
        # 2. 번호 분석 업데이트
        if self.run_script('lotto_analyzer.py', 120):
            success_count += 1
        
        time.sleep(2)
        
        # 3. 고급 분석 실행
        if self.run_script('lotto_advanced_analyzer.py', 300):
            success_count += 1
        
        time.sleep(2)
        
        # 4. 새로운 추천 번호 생성
        if self.run_script('lotto_recommender.py', 120):
            success_count += 1
        
        time.sleep(2)
        
        # 5. 구매 기록 관리
        if self.run_script('lotto_purchase_manager.py', 120):
            success_count += 1
        
        # 결과 요약
        self.log_message("=" * 50)
        self.log_message(f"🎯 업데이트 완료: {success_count}/{total_steps} 성공")
        
        if success_count == total_steps:
            self.log_message("🎉 전체 업데이트 성공!")
            return True
        else:
            self.log_message("⚠️ 일부 업데이트 실패")
            return False
    
    def quick_update(self):
        """빠른 업데이트 (새 회차 확인 + 기본 분석)"""
        self.log_message("⚡ 빠른 업데이트 시작")
        
        if not self.check_new_draw():
            self.log_message("📊 업데이트할 내용이 없습니다.")
            return True
        
        success_count = 0
        
        # 새 당첨번호 수집
        if self.run_script('lotto_crawler.py', 60):
            success_count += 1
        
        # 기본 분석
        if self.run_script('lotto_analyzer.py', 60):
            success_count += 1
        
        # 추천 번호 생성
        if self.run_script('lotto_recommender.py', 60):
            success_count += 1
        
        self.log_message(f"⚡ 빠른 업데이트 완료: {success_count}/3 성공")
        return success_count >= 2
    
    def weekly_maintenance(self):
        """주간 정비 (전체 데이터 검증 + 고급 분석)"""
        self.log_message("🔧 주간 정비 시작")
        
        maintenance_tasks = [
            ('lotto_full_collector.py', 600),  # 전체 데이터 검증
            ('lotto_advanced_analyzer.py', 300),  # 고급 분석
            ('lotto_purchase_manager.py', 120),   # 구매 관리
        ]
        
        success_count = 0
        
        for script, timeout in maintenance_tasks:
            if self.run_script(script, timeout):
                success_count += 1
            time.sleep(5)
        
        self.log_message(f"🔧 주간 정비 완료: {success_count}/{len(maintenance_tasks)} 성공")
        return success_count >= 2

def main():
    import sys
    
    scripts_path = '/volume1/web/lotto/scripts'
    updater = LottoAutoUpdater(scripts_path)
    
    # 실행 모드 결정
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = 'full'
    
    if mode == 'quick':
        updater.quick_update()
    elif mode == 'weekly':
        updater.weekly_maintenance()
    else:
        updater.full_update_cycle()

if __name__ == "__main__":
    main()
