#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, jsonify
import sqlite3
from datetime import datetime
import json
import subprocess
import os

app = Flask(__name__)
DB_PATH = '/volume1/web/lotto/database/lotto.db'
SCRIPTS_PATH = '/volume1/web/lotto/scripts'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

@app.route('/')
def index():
    """로또 분석 메인 대시보드"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 최신 당첨번호 (10회차로 증가)
        cursor.execute("""
            SELECT draw_no, num1, num2, num3, num4, num5, num6, bonus_num, draw_date
            FROM lotto_results ORDER BY draw_no DESC LIMIT 10
        """)
        recent_results = cursor.fetchall()

        # 빈출 번호 TOP 10
        cursor.execute("""
            SELECT number, frequency FROM number_frequency
            ORDER BY frequency DESC LIMIT 10
        """)
        frequent_numbers = cursor.fetchall()

        # 미출현 번호 TOP 10 (제대로 분석되었는지 확인)
        cursor.execute("""
            SELECT number, not_drawn_weeks, last_drawn FROM number_frequency
            ORDER BY not_drawn_weeks DESC LIMIT 10
        """)
        overdue_numbers = cursor.fetchall()

        # 수동 추천 번호 (5개) - type별로 구분
        cursor.execute("""
            SELECT numbers, algorithm, confidence_score, reason
            FROM recommended_numbers
            WHERE algorithm IN ('frequency_based', 'overdue_based', 'hybrid', 'balanced', 'smart_combination')
            ORDER BY created_at DESC LIMIT 5
        """)
        manual_recommendations = cursor.fetchall()

        # 반자동 추천 번호 (2개, 3개씩만)
        cursor.execute("""
            SELECT numbers, algorithm, confidence_score, reason
            FROM recommended_numbers
            WHERE algorithm IN ('semi_auto_frequent', 'semi_auto_overdue')
            ORDER BY created_at DESC LIMIT 2
        """)
        semi_auto_recommendations = cursor.fetchall()

        # 총 회차 수
        cursor.execute("SELECT COUNT(*) FROM lotto_results")
        total_draws = cursor.fetchone()[0]

        # 최신 회차로 미출현 주차 검증
        cursor.execute("SELECT MAX(draw_no) FROM lotto_results")
        latest_draw = cursor.fetchone()[0] or 0

        conn.close()

        template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎲 로또 번호 분석 시스템</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Noto Sans KR', sans-serif;
        }
        .main-container {
            background: rgba(255,255,255,0.95);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            margin: 20px;
            padding: 30px;
        }
        .header-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
        }
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            border-left: 5px solid #667eea;
        }
        .number-ball {
            display: inline-block;
            width: 35px;
            height: 35px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            text-align: center;
            line-height: 35px;
            font-weight: bold;
            margin: 2px;
            font-size: 13px;
        }
        .number-ball-small {
            width: 28px;
            height: 28px;
            line-height: 28px;
            font-size: 11px;
            margin: 1px;
        }
        .bonus-ball {
            background: linear-gradient(135deg, #ff6b6b, #ee5a24) !important;
        }
        .frequent-number { background: linear-gradient(135deg, #00d2d3, #54a0ff) !important; }
        .overdue-number { background: linear-gradient(135deg, #ff9ff3, #f368e0) !important; }
        .recommended-number { background: linear-gradient(135deg, #feca57, #ff9ff3) !important; }
        .semi-auto-number { background: linear-gradient(135deg, #26de81, #20bf6b) !important; }

        .confidence-high { color: #28a745; font-weight: bold; }
        .confidence-medium { color: #ffc107; font-weight: bold; }
        .confidence-low { color: #dc3545; font-weight: bold; }

        .algorithm-badge {
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .algo-hybrid { background: #667eea; color: white; }
        .algo-frequency_based { background: #54a0ff; color: white; }
        .algo-overdue_based { background: #ff6b6b; color: white; }
        .algo-balanced { background: #48CAE4; color: white; }
        .algo-smart_combination { background: #a55eea; color: white; }
        .algo-semi_auto_frequent { background: #26de81; color: white; }
        .algo-semi_auto_overdue { background: #fd79a8; color: white; }

        .compact-result {
            padding: 6px 10px;
            margin-bottom: 6px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 3px solid #667eea;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .draw-info {
            font-size: 0.85em;
            font-weight: bold;
            color: #495057;
            min-width: 120px;
        }

        .numbers-row {
            display: flex;
            align-items: center;
            gap: 2px;
        }

        .status-indicator {
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .status-success { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-info { background: #d1ecf1; color: #0c5460; }

        .recommendation-card {
            margin-bottom: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            border-left: 4px solid #667eea;
        }

        .semi-auto-card {
            background: linear-gradient(135deg, rgba(38, 222, 129, 0.1), rgba(32, 191, 107, 0.1));
            border-left-color: #26de81;
        }
    </style>
</head>
<body>
    <div class="main-container">
        <!-- 헤더 -->
        <div class="header-section">
            <h1 class="display-4"><i class="fas fa-dice"></i> 로또 번호 분석 시스템</h1>
            <p class="lead">AI 기반 로또 번호 분석 및 추천 서비스</p>
            <p><i class="fas fa-calendar"></i> {{ current_time }}</p>
            <p><i class="fas fa-database"></i> 총 {{ total_draws }}회차 데이터 보유 (최신: {{ latest_draw }}회차)</p>
        </div>

        <div class="row">
            <!-- 최신 당첨번호 (10회차, 컴팩트) -->
            <div class="col-lg-7">
                <div class="stat-card">
                    <h4><i class="fas fa-trophy text-warning"></i> 최신 당첨번호 (최근 10회차)</h4>
                    {% if recent_results %}
                        {% for result in recent_results %}
                        <div class="compact-result">
                            <div class="draw-info">{{ result[0] }}회차<br><small class="text-muted">{{ result[8] }}</small></div>
                            <div class="numbers-row">
                                {% for i in range(1, 7) %}
                                    <span class="number-ball number-ball-small">{{ result[i] }}</span>
                                {% endfor %}
                                <span class="mx-1">+</span>
                                <span class="number-ball number-ball-small bonus-ball">{{ result[7] }}</span>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle"></i> 당첨번호 데이터가 없습니다.
                        </div>
                    {% endif %}
                </div>
            </div>

            <!-- 빠른 메뉴 & 시스템 정보 -->
            <div class="col-lg-5">
                <div class="stat-card">
                    <h4><i class="fas fa-cogs text-primary"></i> 빠른 메뉴</h4>
                    <div class="d-grid gap-2">
                        <button class="btn btn-primary" onclick="updateData()">
                            <i class="fas fa-sync-alt"></i> 데이터 업데이트
                        </button>
                        <button class="btn btn-success" onclick="generateRecommendations()">
                            <i class="fas fa-magic"></i> 새 추천 생성
                        </button>
                        <button class="btn btn-info" onclick="runAnalysis()">
                            <i class="fas fa-chart-bar"></i> 번호 분석
                        </button>
                        <button class="btn btn-warning" onclick="window.open('/charts', '_blank')">
                            <i class="fas fa-chart-line"></i> 📊 차트 보기
                        </button>
                    </div>
                </div>

                <div class="stat-card">
                    <h4><i class="fas fa-info-circle text-info"></i> 분석 현황</h4>
                    <div class="small">
                        <p><strong>데이터:</strong> {{ total_draws }}회차</p>
                        <p><strong>최신:</strong> {{ latest_draw }}회차</p>
                        <p><strong>수동 추천:</strong> 5종류</p>
                        <p><strong>반자동:</strong> 2종류</p>
                        <div class="mt-2">
                            <span class="status-indicator status-success">
                                <i class="fas fa-check"></i> 정상 운영
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <!-- 빈출 번호 -->
            <div class="col-md-6">
                <div class="stat-card">
                    <h4><i class="fas fa-fire text-danger"></i> 빈출 번호 TOP 10</h4>
                    {% if frequent_numbers %}
                        <div class="mb-3">
                            {% for num, freq in frequent_numbers %}
                                <span class="frequent-number number-ball" title="{{ freq }}회 출현">{{ num }}</span>
                            {% endfor %}
                        </div>
                        <table class="table table-sm">
                            <thead>
                                <tr><th>번호</th><th>출현횟수</th><th>확률</th></tr>
                            </thead>
                            <tbody>
                                {% for num, freq in frequent_numbers[:5] %}
                                <tr>
                                    <td><strong>{{ num }}번</strong></td>
                                    <td>{{ freq }}회</td>
                                    <td>{{ "%.1f"|format((freq / total_draws) * 100 if total_draws > 0 else 0) }}%</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    {% else %}
                        <div class="alert alert-info">분석 데이터가 없습니다.</div>
                    {% endif %}
                </div>
            </div>

            <!-- 미출현 번호 (검증된 데이터) -->
            <div class="col-md-6">
                <div class="stat-card">
                    <h4><i class="fas fa-hourglass-half text-primary"></i> 미출현 번호 TOP 10</h4>
                    <small class="text-muted">최신 {{ latest_draw }}회차 기준</small>
                    {% if overdue_numbers %}
                        <div class="mb-3 mt-2">
                            {% for num, weeks, last_drawn in overdue_numbers %}
                                <span class="overdue-number number-ball" title="{{ num }}번: {{ weeks }}주차 전 ({{ last_drawn }}회차)">{{ num }}</span>
                            {% endfor %}
                        </div>
                        <table class="table table-sm">
                            <thead>
                                <tr><th>번호</th><th>미출현</th><th>마지막</th><th>상태</th></tr>
                            </thead>
                            <tbody>
                                {% for num, weeks, last_drawn in overdue_numbers[:5] %}
                                <tr>
                                    <td><strong>{{ num }}번</strong></td>
                                    <td>{{ weeks }}주차</td>
                                    <td>{{ last_drawn }}회차</td>
                                    <td>
                                        {% if weeks > 20 %}
                                            <span class="badge bg-danger">초장기</span>
                                        {% elif weeks > 10 %}
                                            <span class="badge bg-warning">장기</span>
                                        {% else %}
                                            <span class="badge bg-info">일반</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    {% else %}
                        <div class="alert alert-info">분석 데이터가 없습니다.</div>
                    {% endif %}
                </div>
            </div>
        </div>

        <!-- 수동 구매 추천 번호 (5개) -->
        <div class="stat-card">
            <h4><i class="fas fa-hand-pointer text-success"></i> 수동 구매 추천 번호 (5세트)</h4>
            <p class="text-muted">다양한 알고리즘으로 분석한 수동 구매용 추천 번호들입니다.</p>

            {% if manual_recommendations %}
                <div class="row">
                    {% for numbers_str, algorithm, confidence, reason in manual_recommendations %}
                    {% set numbers = numbers_str.split(',') %}
                    <div class="col-md-6 col-lg-4">
                        <div class="recommendation-card">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="algorithm-badge algo-{{ algorithm.lower() }}">
                                    {{ algorithm.replace('_', ' ').title() }}
                                </span>
                                <span class="{% if confidence >= 80 %}confidence-high{% elif confidence >= 70 %}confidence-medium{% else %}confidence-low{% endif %}">
                                    {{ confidence }}%
                                </span>
                            </div>
                            <div class="mb-2">
                                {% for num in numbers %}
                                    <span class="recommended-number number-ball number-ball-small">{{ num.strip() }}</span>
                                {% endfor %}
                            </div>
                            <small class="text-muted">{{ reason }}</small>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> 수동 추천 번호가 없습니다. '새 추천 생성' 버튼을 클릭해주세요.
                </div>
            {% endif %}
        </div>

        <!-- 반자동 구매 추천 번호 (2개, 3개씩) -->
        <div class="stat-card">
            <h4><i class="fas fa-magic text-info"></i> 반자동 구매 추천 (3개씩 고정, 2세트)</h4>
            <p class="text-muted">고신뢰도 알고리즘으로 선별된 반자동 구매용 번호 3개씩입니다. 나머지 3개는 자동 선택하세요.</p>

            {% if semi_auto_recommendations %}
                <div class="row">
                    {% for numbers_str, algorithm, confidence, reason in semi_auto_recommendations %}
                    {% set all_numbers = numbers_str.split(',') %}
                    {% set selected_numbers = all_numbers[:3] %}
                    <div class="col-md-6">
                        <div class="recommendation-card semi-auto-card">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="algorithm-badge algo-{{ algorithm.lower() }}">
                                    {{ algorithm.replace('_', ' ').replace('semi auto', '반자동').title() }}
                                </span>
                                <span class="confidence-high">{{ confidence }}%</span>
                            </div>
                            <div class="mb-2">
                                {% for num in selected_numbers %}
                                    <span class="semi-auto-number number-ball">{{ num.strip() }}</span>
                                {% endfor %}
                                <span class="ms-2 text-success fw-bold">+ 자동 3개</span>
                            </div>
                            <small class="text-muted">{{ reason }}</small>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> 반자동 추천 번호가 없습니다.
                </div>
            {% endif %}
        </div>

        <!-- 하단 메뉴 -->
        <div class="text-center mt-4">
            <div class="row">
                <div class="col-md-4">
                    <button class="btn btn-outline-primary w-100" onclick="updateData()">
                        <i class="fas fa-sync-alt"></i> 데이터 업데이트
                    </button>
                </div>
                <div class="col-md-4">
                    <button class="btn btn-outline-success w-100" onclick="generateRecommendations()">
                        <i class="fas fa-magic"></i> 새 추천 생성
                    </button>
                </div>
                <div class="col-md-4">
                    <button class="btn btn-outline-info w-100" onclick="runAnalysis()">
                        <i class="fas fa-cogs"></i> 번호 분석
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js"></script>

    <script>
        function showLoading(button) {
            const originalText = button.innerHTML;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 처리중...';
            button.disabled = true;
            return originalText;
        }

        function hideLoading(button, originalText) {
            button.innerHTML = originalText;
            button.disabled = false;
        }

        function updateData() {
            if (confirm('최신 당첨번호를 수집하시겠습니까?')) {
                const button = event.target;
                const originalText = showLoading(button);

                fetch('/api/update_data', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        hideLoading(button, originalText);
                        alert(data.message);
                        if (data.success) location.reload();
                    })
                    .catch(error => {
                        hideLoading(button, originalText);
                        alert('오류가 발생했습니다: ' + error);
                    });
            }
        }

        function generateRecommendations() {
            if (confirm('새로운 추천 번호를 생성하시겠습니까?')) {
                const button = event.target;
                const originalText = showLoading(button);

                fetch('/api/generate_recommendations', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        hideLoading(button, originalText);
                        alert(data.message);
                        if (data.success) location.reload();
                    })
                    .catch(error => {
                        hideLoading(button, originalText);
                        alert('오류가 발생했습니다: ' + error);
                    });
            }
        }

        function runAnalysis() {
            if (confirm('번호 분석을 실행하시겠습니까?')) {
                const button = event.target;
                const originalText = showLoading(button);

                fetch('/api/run_analysis', {method: 'POST'})
                    .then(response => response.json())
                    .then(data => {
                        hideLoading(button, originalText);
                        alert(data.message);
                        if (data.success) location.reload();
                    })
                    .catch(error => {
                        hideLoading(button, originalText);
                        alert('오류가 발생했습니다: ' + error);
                    });
            }
        }
    </script>
</body>
</html>
        '''

        return render_template_string(template,
            recent_results=recent_results,
            frequent_numbers=frequent_numbers,
            overdue_numbers=overdue_numbers,
            manual_recommendations=manual_recommendations,
            semi_auto_recommendations=semi_auto_recommendations,
            total_draws=total_draws,
            latest_draw=latest_draw,
            current_time=datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')
        )

    except Exception as e:
        return f'<h1>오류 발생</h1><p>{str(e)}</p>'

# 나머지 API 라우트들 (기존과 동일하지만 새 추천 시스템 사용)
@app.route('/api/generate_recommendations', methods=['POST'])
def api_generate_recommendations():
    """새 추천 번호 생성 API (강화버전 사용)"""
    try:
        script_path = os.path.join(SCRIPTS_PATH, 'lotto_recommender_enhanced.py')
        result = subprocess.run(['python3', script_path],
                              capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return jsonify({'success': True, 'message': '새로운 추천 번호가 생성되었습니다! (5개 수동 + 2개 반자동)'})
        else:
            error_msg = result.stderr if result.stderr else '알 수 없는 오류'
            return jsonify({'success': False, 'message': f'추천 생성 실패: {error_msg}'})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '추천 생성 시간 초과 (1분)'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'추천 생성 오류: {str(e)}'})

# 기존 API들도 그대로 포함 (생략)

if __name__ == '__main__':
    print("🎲 로또 분석 웹 대시보드 시작... (강화버전)")
    print("🌐 브라우저에서 http://localhost:8080 에 접속하세요")
    print("📁 스크립트 경로:", SCRIPTS_PATH)
    print("🗄️ 데이터베이스 경로:", DB_PATH)
    app.run(host='0.0.0.0', port=8080, debug=False)
