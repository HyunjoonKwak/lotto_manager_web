#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime

class LottoDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
    
    def create_tables(self):
        """로또 관련 테이블 생성"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 로또 당첨 번호 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS lotto_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw_no INTEGER UNIQUE NOT NULL,
                    draw_date TEXT NOT NULL,
                    num1 INTEGER NOT NULL,
                    num2 INTEGER NOT NULL,
                    num3 INTEGER NOT NULL,
                    num4 INTEGER NOT NULL,
                    num5 INTEGER NOT NULL,
                    num6 INTEGER NOT NULL,
                    bonus_num INTEGER NOT NULL,
                    total_sales BIGINT DEFAULT 0,
                    winner_1st INTEGER DEFAULT 0,
                    prize_1st BIGINT DEFAULT 0,
                    winner_2nd INTEGER DEFAULT 0,
                    prize_2nd BIGINT DEFAULT 0,
                    winner_3rd INTEGER DEFAULT 0,
                    prize_3rd BIGINT DEFAULT 0,
                    winner_4th INTEGER DEFAULT 0,
                    prize_4th BIGINT DEFAULT 0,
                    winner_5th INTEGER DEFAULT 0,
                    prize_5th BIGINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 번호 출현 빈도 분석 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS number_frequency (
                    number INTEGER PRIMARY KEY,
                    frequency INTEGER DEFAULT 0,
                    last_drawn TEXT,
                    not_drawn_weeks INTEGER DEFAULT 0,
                    bonus_frequency INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 추천 번호 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommended_numbers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    week_no INTEGER NOT NULL,
                    numbers TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    confidence_score REAL DEFAULT 0.0,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 구매 기록 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw_no INTEGER NOT NULL,
                    numbers TEXT NOT NULL,
                    purchase_amount INTEGER NOT NULL,
                    auto_purchase BOOLEAN DEFAULT 0,
                    result_checked BOOLEAN DEFAULT 0,
                    matched_count INTEGER DEFAULT 0,
                    prize_amount INTEGER DEFAULT 0,
                    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 패턴 분석 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT NOT NULL,
                    pattern_value TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    last_seen TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            
            # 번호 빈도 테이블 초기화 (1~45번)
            for num in range(1, 46):
                cursor.execute("""
                    INSERT OR IGNORE INTO number_frequency (number, frequency, not_drawn_weeks)
                    VALUES (?, 0, 0)
                """, (num,))
            
            conn.commit()
            conn.close()
            
            print("✅ 데이터베이스 테이블 생성 완료")
            return True
            
        except Exception as e:
            print(f"❌ 데이터베이스 생성 실패: {str(e)}")
            return False

def main():
    print("🗄️ 로또 데이터베이스 초기화")
    
    db_path = '/volume1/web/lotto/database/lotto.db'
    lotto_db = LottoDatabase(db_path)
    
    if lotto_db.create_tables():
        print("🎉 데이터베이스 초기화 완료!")
    else:
        print("❌ 데이터베이스 초기화 실패")

if __name__ == "__main__":
    main()
