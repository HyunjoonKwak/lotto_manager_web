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

        # 최신 당첨번호
        cursor.execute("""
            SELECT draw_no, num1, num2, num3, num4, num5, num6, bonus_num, draw_date
            FROM lotto_results ORDER BY draw_no DESC LIMIT 5
        """)
        recent_results = cursor.fetchall()

        # 빈출 번호 TOP 10
        cursor.execute("""
            SELECT number, frequency FROM number_frequency
            ORDER BY frequency DESC LIMIT 10
        """)
        frequent_numbers = cursor.fetchall()

        # 미출현 번호 TOP 10
        cursor.execute("""
            SELECT number, not_drawn_weeks FROM number_frequency
            ORDER BY not_drawn_weeks DESC LIMIT 10
        """)
        overdue_numbers = cursor.fetchall()

        # 추천 번호
        cursor.execute("""
            SELECT numbers, algorithm, confidence_score, reason
            FROM recommended_numbers
            ORDER BY created_at DESC LIMIT 5
        """)
        recommendations = cursor.fetchall()

        # 총 회차 수
        cursor.execute("SELECT COUNT(*) FROM lotto_results")
        total_draws = cursor.fetchone()[0]

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
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            text-align: center;
            line-height: 40px;
            font-weight: bold;
            margin: 2px;
            font-size: 14px;
        }
        .bonus-ball {
            background: linear-gradient(135deg, #ff6b6b, #ee5a24) !important;
        }
        .frequent-number { background: linear-gradient(135deg, #00d2d3, #54a0ff) !important; }
        .overdue-number { background: linear-gradient(135deg, #ff9ff3, #f368e0) !important; }
        .recommended-number { background: linear-gradient(135deg, #feca57, #ff9ff3) !important; }

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

        .status-indicator {
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .status-success { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-info { background: #d1ecf1; color: #0c5460; }
    </style>
</head>
<body>
    <div class="main-container">
        <!-- 헤더 -->
        <div class="header-section">
            <h1 class="display-4"><i class="fas fa-dice"></i> 로또 번호 분석 시스템</h1>
            <p class="lead">AI 기반 로또 번호 분석 및 추천 서비스</p>
            <p><i class="fas fa-calendar"></i> {{ current_time }}</p>
            <p><i class="fas fa-database"></i> 총 {{ total_draws }}회차 데이터 보유</p>
        </div>

        <div class="row">
            <!-- 최신 당첨번호 -->
            <div class="col-lg-8">
                <div class="stat-card">
                    <h4><i class="fas fa-trophy text-warning"></i> 최신 당첨번호</h4>
                    {% if recent_results %}
                        {% for result in recent_results %}
                        <div class="mb-3 p-3 bg-light rounded">
                            <strong>{{ result[0] }}회차</strong>
                            <span class="text-muted">({{ result[8] }})</span>
                            <div class="mt-2">
                                {% for i in range(1, 7) %}
                                    <span class="number-ball">{{ result[i] }}</span>
                                {% endfor %}
                                <span class="mx-2">+</span>
                                <span class="number-ball bonus-ball">{{ result[7] }}</span>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle"></i> 당첨번호 데이터가 없습니다. 데이터 업데이트를 실행해주세요.
                        </div>
                    {% endif %}
                </div>
            </div>

            <!-- 빠른 메뉴 -->
            <div class="col-lg-4">
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
                    <h4><i class="fas fa-info-circle text-info"></i> 시스템 정보</h4>
                    <div class="small">
                        <p><strong>데이터 현황:</strong> {{ total_draws }}회차</p>
                        <p><strong>최신 업데이트:</strong> {{ current_time.split()[0] }}</p>
                        <p><strong>추천 알고리즘:</strong> 4종류</p>
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

            <!-- 미출현 번호 -->
            <div class="col-md-6">
                <div class="stat-card">
                    <h4><i class="fas fa-hourglass-half text-primary"></i> 미출현 번호 TOP 10</h4>
                    {% if overdue_numbers %}
                        <div class="mb-3">
                            {% for num, weeks in overdue_numbers %}
                                <span class="overdue-number number-ball" title="{{ weeks }}주차 전">{{ num }}</span>
                            {% endfor %}
                        </div>
                        <table class="table table-sm">
                            <thead>
                                <tr><th>번호</th><th>미출현</th><th>상태</th></tr>
                            </thead>
                            <tbody>
                                {% for num, weeks in overdue_numbers[:5] %}
                                <tr>
                                    <td><strong>{{ num }}번</strong></td>
                                    <td>{{ weeks }}주차</td>
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

        <!-- AI 추천 번호 -->
        <div class="stat-card">
            <h4><i class="fas fa-robot text-success"></i> AI 추천 번호</h4>
            <p class="text-muted">다양한 알고리즘으로 분석한 추천 번호들입니다.</p>

            {% if recommendations %}
                {% for numbers_str, algorithm, confidence, reason in recommendations %}
                {% set numbers = numbers_str.split(',') %}
                <div class="mb-4 p-3 bg-light rounded">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <span class="algorithm-badge algo-{{ algorithm.lower() }}">
                                {{ algorithm.upper() }}
                            </span>
                            <span class="ms-2 {% if confidence >= 80 %}confidence-high{% elif confidence >= 70 %}confidence-medium{% else %}confidence-low{% endif %}">
                                신뢰도 {{ confidence }}%
                            </span>
                        </div>
                    </div>
                    <div class="mb-2">
                        {% for num in numbers %}
                            <span class="recommended-number number-ball">{{ num.strip() }}</span>
                        {% endfor %}
                    </div>
                    <small class="text-muted">{{ reason }}</small>
                </div>
                {% endfor %}
            {% else %}
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> 추천 번호가 없습니다. '새 추천 생성' 버튼을 클릭해주세요.
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
            recommendations=recommendations,
            total_draws=total_draws,
            current_time=datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')
        )

    except Exception as e:
        return f'<h1>오류 발생</h1><p>{str(e)}</p>'

@app.route('/charts')
def charts_page():
    """차트 분석 페이지"""
    template = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 로또 분석 차트</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.min.js"></script>
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .chart-container { background: white; border-radius: 15px; padding: 20px; margin: 20px 0; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .header { background: rgba(255,255,255,0.95); border-radius: 15px; padding: 20px; margin: 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="header">
            <h1>📊 로또 번호 분석 차트</h1>
            <a href="/" class="btn btn-primary">← 메인 대시보드로</a>
        </div>

        <div class="row">
            <div class="col-lg-6">
                <div class="chart-container">
                    <h4>📈 번호별 출현 빈도</h4>
                    <canvas id="frequencyChart"></canvas>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="chart-container">
                    <h4>🎯 구간별 분포</h4>
                    <canvas id="zoneChart"></canvas>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-12">
                <div class="chart-container">
                    <h4>📉 최근 당첨번호 합계 추이</h4>
                    <canvas id="sumTrendChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            loadCharts();
        });

        function loadCharts() {
            fetch('/api/chart_data')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        console.error('데이터 로드 오류:', data.error);
                        return;
                    }
                    createFrequencyChart(data.frequency_data);
                    createZoneChart(data.zone_distribution);
                    createSumTrendChart(data.sum_trend);
                })
                .catch(error => console.error('차트 로드 실패:', error));
        }

        function createFrequencyChart(data) {
            const ctx = document.getElementById('frequencyChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.number + '번'),
                    datasets: [{
                        label: '출현 횟수',
                        data: data.map(d => d.frequency),
                        backgroundColor: 'rgba(102, 126, 234, 0.6)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: { y: { beginAtZero: true } }
                }
            });
        }

        function createZoneChart(data) {
            const ctx = document.getElementById('zoneChart').getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.map(d => d.zone),
                    datasets: [{
                        data: data.map(d => d.frequency),
                        backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56']
                    }]
                },
                options: { responsive: true }
            });
        }

        function createSumTrendChart(data) {
            const ctx = document.getElementById('sumTrendChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => d.draw + '회'),
                    datasets: [{
                        label: '당첨번호 합계',
                        data: data.map(d => d.sum),
                        borderColor: '#FF6384',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: { responsive: true }
            });
        }
    </script>
</body>
</html>
    '''
    return render_template_string(template)

@app.route('/api/chart_data')
def api_chart_data():
    """차트용 데이터 API"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 번호별 출현 빈도
        cursor.execute("""
            SELECT number, frequency FROM number_frequency
            ORDER BY number
        """)
        frequency_data = [{'number': row[0], 'frequency': row[1]} for row in cursor.fetchall()]

        # 최근 20회차 합계 추이
        cursor.execute("""
            SELECT draw_no, (num1 + num2 + num3 + num4 + num5 + num6) as total_sum
            FROM lotto_results
            ORDER BY draw_no DESC
            LIMIT 20
        """)
        sum_trend = [{'draw': row[0], 'sum': row[1]} for row in cursor.fetchall()]
        sum_trend.reverse()

        # 구간별 분포
        cursor.execute("""
            SELECT
                CASE
                    WHEN number BETWEEN 1 AND 15 THEN '1-15구간'
                    WHEN number BETWEEN 16 AND 30 THEN '16-30구간'
                    ELSE '31-45구간'
                END as zone,
                SUM(frequency) as total_freq
            FROM number_frequency
            GROUP BY zone
            ORDER BY zone
        """)
        zone_distribution = [{'zone': row[0], 'frequency': row[1]} for row in cursor.fetchall()]

        conn.close()

        return jsonify({
            'frequency_data': frequency_data,
            'sum_trend': sum_trend,
            'zone_distribution': zone_distribution
        })

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/update_data', methods=['POST'])
def api_update_data():
    """데이터 업데이트 API"""
    try:
        script_path = os.path.join(SCRIPTS_PATH, 'lotto_crawler.py')
        result = subprocess.run(['python3', script_path],
                              capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            return jsonify({'success': True, 'message': '데이터 업데이트 완료!'})
        else:
            error_msg = result.stderr if result.stderr else '알 수 없는 오류'
            return jsonify({'success': False, 'message': f'업데이트 실패: {error_msg}'})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '업데이트 시간 초과 (2분)'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'업데이트 오류: {str(e)}'})

@app.route('/api/generate_recommendations', methods=['POST'])
def api_generate_recommendations():
    """새 추천 번호 생성 API"""
    try:
        script_path = os.path.join(SCRIPTS_PATH, 'lotto_recommender.py')
        result = subprocess.run(['python3', script_path],
                              capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return jsonify({'success': True, 'message': '새로운 추천 번호가 생성되었습니다!'})
        else:
            error_msg = result.stderr if result.stderr else '알 수 없는 오류'
            return jsonify({'success': False, 'message': f'추천 생성 실패: {error_msg}'})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '추천 생성 시간 초과 (1분)'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'추천 생성 오류: {str(e)}'})

@app.route('/api/run_analysis', methods=['POST'])
def api_run_analysis():
    """번호 분석 실행 API"""
    try:
        script_path = os.path.join(SCRIPTS_PATH, 'lotto_analyzer.py')
        result = subprocess.run(['python3', script_path],
                              capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return jsonify({'success': True, 'message': '번호 분석 완료!'})
        else:
            error_msg = result.stderr if result.stderr else '알 수 없는 오류'
            return jsonify({'success': False, 'message': f'분석 실패: {error_msg}'})
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '분석 시간 초과 (1분)'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'분석 오류: {str(e)}'})

if __name__ == '__main__':
    print("🎲 로또 분석 웹 대시보드 시작...")
    print("🌐 브라우저에서 http://localhost:8080 에 접속하세요")
    print("📁 스크립트 경로:", SCRIPTS_PATH)
    print("🗄️ 데이터베이스 경로:", DB_PATH)
    app.run(host='0.0.0.0', port=8080, debug=False)
