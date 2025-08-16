#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import random
from datetime import datetime
import math

class LottoRecommender:
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
            weight = max(1, frequency)  # 최소 가중치 1
            weighted_numbers.extend([num] * weight)
        
        selected = []
        attempts = 0
        while len(selected) < 6 and attempts < 1000:
            num = random.choice(weighted_numbers)
            if num not in selected:
                selected.append(num)
            attempts += 1
        
        # 6개 미만이면 랜덤으로 채우기
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
            weight = max(1, not_drawn_weeks // 3)  # 3주마다 가중치 1 증가
            weighted_numbers.extend([num] * weight)
        
        selected = []
        attempts = 0
        while len(selected) < 6 and attempts < 1000:
            num = random.choice(weighted_numbers)
            if num not in selected:
                selected.append(num)
            attempts += 1
        
        # 6개 미만이면 랜덤으로 채우기
        while len(selected) < 6:
            num = random.randint(1, 45)
            if num not in selected:
                selected.append(num)
        
        return sorted(selected)
    
    def hybrid_recommendation(self):
        """하이브리드 추천 (빈도 + 미출현)"""
        stats, total_draws = self.get_number_statistics()
        
        if not stats or total_draws == 0:
            return sorted(random.sample(range(1, 46), 6))
        
        # 종합 점수 계산
        scores = {}
        max_freq = max(stats[num].get('frequency', 0) for num in range(1, 46))
        max_not_drawn = max(stats[num].get('not_drawn_weeks', 0) for num in range(1, 46))
        
        for num in range(1, 46):
            frequency = stats.get(num, {}).get('frequency', 0)
            not_drawn = stats.get(num, {}).get('not_drawn_weeks', 0)
            
            # 정규화된 점수 (0-100)
            freq_score = (frequency / max(1, max_freq)) * 50 if max_freq > 0 else 0
            overdue_score = (not_drawn / max(1, max_not_drawn)) * 50 if max_not_drawn > 0 else 0
            
            scores[num] = freq_score * 0.3 + overdue_score * 0.7  # 미출현에 더 높은 가중치
        
        # 점수 기반 가중 선택
        weighted_numbers = []
        for num, score in scores.items():
            weight = max(1, int(score * 2))  # 점수에 비례한 가중치
            weighted_numbers.extend([num] * weight)
        
        selected = []
        attempts = 0
        while len(selected) < 6 and attempts < 1000:
            num = random.choice(weighted_numbers)
            if num not in selected:
                selected.append(num)
            attempts += 1
        
        # 6개 미만이면 랜덤으로 채우기
        while len(selected) < 6:
            num = random.randint(1, 45)
            if num not in selected:
                selected.append(num)
        
        return sorted(selected)
    
    def balanced_recommendation(self):
        """균형 추천 (홀짝, 구간 고려)"""
        selected = []
        
        # 홀수 3개, 짝수 3개로 균형
        odds = [i for i in range(1, 46, 2)]  # 홀수
        evens = [i for i in range(2, 46, 2)]  # 짝수
        
        selected.extend(random.sample(odds, 3))
        selected.extend(random.sample(evens, 3))
        
        return sorted(selected)
    
    def generate_recommendations(self):
        """다양한 알고리즘으로 추천 번호 생성"""
        algorithms = {
            'frequency_based': ('빈도 기반', self.frequency_based_recommendation, 75),
            'overdue_based': ('미출현 기반', self.overdue_based_recommendation, 70),
            'hybrid': ('하이브리드', self.hybrid_recommendation, 85),
            'balanced': ('균형 조합', self.balanced_recommendation, 65)
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
                    'reason': reason
                })
                
            except Exception as e:
                print(f"⚠️ {algo_name} 알고리즘 실패: {str(e)}")
                # 실패시 랜덤 번호로 대체
                numbers = sorted(random.sample(range(1, 46), 6))
                recommendations.append({
                    'algorithm': algo_key,
                    'name': f"{algo_name} (랜덤)",
                    'numbers': numbers,
                    'confidence': 50,
                    'reason': f"{algo_name} 실패로 랜덤 생성"
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
            
            # 기존 추천 삭제 (같은 회차)
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
    print("🤖 로또 번호 AI 추천 시스템")
    print("=" * 50)
    
    db_path = '/volume1/web/lotto/database/lotto.db'
    recommender = LottoRecommender(db_path)
    
    print("🎯 다양한 알고리즘으로 번호 추천 중...")
    recommendations = recommender.generate_recommendations()
    
    print(f"\n🎲 추천 번호 결과 ({len(recommendations)}개 세트):")
    print("=" * 60)
    
    for i, rec in enumerate(recommendations, 1):
        numbers_str = ' - '.join([f'{n:2d}' for n in rec['numbers']])
        print(f"{i}. [{rec['name']}] 신뢰도 {rec['confidence']}%")
        print(f"   번호: {numbers_str}")
        print(f"   이유: {rec['reason']}")
        print()
    
    # 데이터베이스에 저장
    recommender.save_recommendations(recommendations)
    
    print("🎉 로또 번호 추천 완료!")

if __name__ == "__main__":
    main()
