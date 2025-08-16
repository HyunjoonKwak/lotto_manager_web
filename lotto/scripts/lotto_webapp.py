#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify
import subprocess, os
from config import FLASK_HOST, FLASK_PORT, SCRIPTS_PATH, DB_PATH, ensure_dirs
from db import get_conn
from datetime import datetime, timedelta

app = Flask(__name__, template_folder="../templates", static_folder="../static")

@app.route("/")
def index():
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT draw_no, num1, num2, num3, num4, num5, num6, bonus_num, draw_date
            FROM lotto_results ORDER BY draw_no DESC LIMIT 10
        """)
        recent_results = cur.fetchall()

        cur.execute("""
            SELECT number, frequency FROM number_frequency
            ORDER BY frequency DESC, number ASC LIMIT 10
        """)
        frequent_numbers = cur.fetchall()

        cur.execute("""
            SELECT number, not_drawn_weeks, last_drawn
            FROM number_frequency
            ORDER BY not_drawn_weeks DESC, number ASC LIMIT 10
        """)
        overdue_numbers = cur.fetchall()

        cur.execute("""
            SELECT numbers, algorithm, confidence_score, reason, created_at
            FROM recommended_numbers
            ORDER BY created_at DESC LIMIT 7
        """)
        recommendations = cur.fetchall()

        cur.execute("SELECT COUNT(*), MAX(draw_no) FROM lotto_results")
        total_draws, latest_draw = cur.fetchone()

    return render_template("index.html",
                           recent_results=recent_results,
                           frequent_numbers=frequent_numbers,
                           overdue_numbers=overdue_numbers,
                           recommendations=recommendations,
                           total_draws=total_draws or 0,
                           latest_draw=latest_draw or 0)

@app.route("/api/generate_recommendations", methods=["POST"])
def api_generate_recommendations():
    script_path = os.path.join(SCRIPTS_PATH, "lotto_recommender.py")
    try:
        result = subprocess.run(["python3", script_path],
                                capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return jsonify(success=True, message="새 추천 번호 생성 완료")
        return jsonify(success=False, message=f"실패: {result.stderr or '알 수 없는 오류'}")
    except subprocess.TimeoutExpired:
        return jsonify(success=False, message="추천 생성 시간 초과(60s)")
    except Exception as e:
        return jsonify(success=False, message=f"오류: {e}")

@app.route("/api/statistics")
def api_statistics():
    """통계 정보 API"""
    with get_conn() as conn:
        cur = conn.cursor()
        
        # 기본 통계
        cur.execute("SELECT COUNT(*), MAX(draw_no) FROM lotto_results")
        total_draws, latest_draw = cur.fetchone()
        
        # 최근 30일 통계
        thirty_days_ago = datetime.now() - timedelta(days=30)
        cur.execute("""
            SELECT COUNT(*) FROM lotto_results 
            WHERE draw_date >= ?
        """, (thirty_days_ago.strftime('%Y-%m-%d'),))
        recent_draws = cur.fetchone()[0]
        
        # 번호별 통계
        cur.execute("""
            SELECT number, frequency, not_drawn_weeks 
            FROM number_frequency 
            ORDER BY frequency DESC
        """)
        number_stats = cur.fetchall()
        
        # 추천 번호 통계
        cur.execute("SELECT COUNT(*) FROM recommended_numbers")
        total_recommendations = cur.fetchone()[0]
        
        return jsonify({
            'total_draws': total_draws or 0,
            'latest_draw': latest_draw or 0,
            'recent_draws': recent_draws,
            'total_recommendations': total_recommendations,
            'number_stats': [
                {
                    'number': row[0],
                    'frequency': row[1],
                    'not_drawn_weeks': row[2]
                } for row in number_stats
            ]
        })

@app.route("/api/recent_results")
def api_recent_results():
    """최근 당첨 결과 API"""
    limit = request.args.get('limit', 10, type=int)
    
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT draw_no, num1, num2, num3, num4, num5, num6, bonus_num, draw_date
            FROM lotto_results ORDER BY draw_no DESC LIMIT ?
        """, (limit,))
        results = cur.fetchall()
        
        return jsonify({
            'results': [
                {
                    'draw_no': row[0],
                    'numbers': [row[1], row[2], row[3], row[4], row[5], row[6]],
                    'bonus_num': row[7],
                    'draw_date': row[8]
                } for row in results
            ]
        })

@app.route("/api/number_analysis/<int:number>")
def api_number_analysis(number):
    """특정 번호 분석 API"""
    if not 1 <= number <= 45:
        return jsonify({'error': '유효하지 않은 번호입니다 (1-45)'}), 400
    
    with get_conn() as conn:
        cur = conn.cursor()
        
        # 번호 통계
        cur.execute("""
            SELECT frequency, not_drawn_weeks, last_drawn
            FROM number_frequency WHERE number = ?
        """, (number,))
        stats = cur.fetchone()
        
        if not stats:
            return jsonify({'error': '번호 정보를 찾을 수 없습니다'}), 404
        
        # 최근 출현 기록
        cur.execute("""
            SELECT draw_no, draw_date FROM lotto_results
            WHERE num1 = ? OR num2 = ? OR num3 = ? OR num4 = ? OR num5 = ? OR num6 = ? OR bonus_num = ?
            ORDER BY draw_no DESC LIMIT 10
        """, (number, number, number, number, number, number, number))
        recent_appearances = cur.fetchall()
        
        return jsonify({
            'number': number,
            'frequency': stats[0],
            'not_drawn_weeks': stats[1],
            'last_drawn': stats[2],
            'recent_appearances': [
                {'draw_no': row[0], 'draw_date': row[1]} 
                for row in recent_appearances
            ]
        })

@app.route("/api/search_draws")
def api_search_draws():
    """회차 검색 API"""
    draw_no = request.args.get('draw_no', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    if not any([draw_no, date_from, date_to]):
        return jsonify({'error': '검색 조건을 입력해주세요'}), 400
    
    with get_conn() as conn:
        cur = conn.cursor()
        
        query = """
            SELECT draw_no, num1, num2, num3, num4, num5, num6, bonus_num, draw_date
            FROM lotto_results WHERE 1=1
        """
        params = []
        
        if draw_no:
            query += " AND draw_no = ?"
            params.append(draw_no)
        
        if date_from:
            query += " AND draw_date >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND draw_date <= ?"
            params.append(date_to)
        
        query += " ORDER BY draw_no DESC LIMIT 50"
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        return jsonify({
            'results': [
                {
                    'draw_no': row[0],
                    'numbers': [row[1], row[2], row[3], row[4], row[5], row[6]],
                    'bonus_num': row[7],
                    'draw_date': row[8]
                } for row in results
            ]
        })

@app.route("/api/health")
def api_health():
    """헬스 체크 API"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'database': db_status
    })

if __name__ == "__main__":
    ensure_dirs()
    print(f"🎲 Lotto web running: http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)
