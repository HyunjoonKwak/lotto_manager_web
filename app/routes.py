from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app, flash, abort
import re
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
import threading
import time
import secrets
from datetime import timedelta, datetime
from typing import Optional, List

from .extensions import db, csrf
from .models import Draw, WinningShop, Purchase, User, PasswordResetToken, RecommendationSet
from .services.lotto_fetcher import fetch_draw, fetch_winning_shops
from .services.updater import (
    perform_update as svc_perform_update,
    update_range as svc_update_range,
    get_latest_round,
    update_missing_rounds,
    update_to_latest
)
from .services.recommender import auto_recommend, semi_auto_recommend, enhanced_auto_recommend
from .services.analyzer import (
    get_number_frequency, get_most_frequent_numbers, get_least_frequent_numbers,
    analyze_patterns, get_hot_cold_analysis, get_number_combinations
)
from .services.lottery_checker import (
    check_all_pending_results, get_purchase_statistics,
    get_recent_purchases_with_results, update_purchase_results
)
from .services.recommendation_manager import (
    get_persistent_recommendations, refresh_recommendations
)
from .services.qr_parser import (
    parse_lotto_qr_url, parse_qr_data_to_purchases
)


main_bp = Blueprint("main", __name__)


def is_mobile_device():
    """모바일 기기 감지"""
    user_agent = request.headers.get('User-Agent', '').lower()
    mobile_patterns = [
        r'mobile', r'android', r'iphone', r'ipad', r'ipod',
        r'blackberry', r'windows phone', r'opera mini',
        r'mobile safari', r'kindle', r'webos'
    ]

    for pattern in mobile_patterns:
        if re.search(pattern, user_agent):
            return True
    return False


def mobile_redirect_check():
    """모바일 기기면 모바일 페이지로 리다이렉트"""
    # 데스크톱 강제 모드 체크
    if request.args.get('desktop') == '1':
        return False

    # 이미 모바일 경로면 리다이렉트 안함
    if request.endpoint and 'mobile' in request.endpoint:
        return False

    return is_mobile_device()


def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))
        if not current_user.has_admin_role():
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

# Progress tracking storage
crawling_progress = {
    "is_running": False,
    "should_stop": False,
    "current_round": 0,
    "total_rounds": 0,
    "completed_rounds": 0,
    "status": "대기중",
    "start_time": None,
    "operation_type": ""
}


def _update_progress(current_round=0, total_rounds=0, completed_rounds=0, status="진행중", operation_type="", is_running=True):
    """Update crawling progress status"""
    crawling_progress["current_round"] = current_round
    crawling_progress["total_rounds"] = total_rounds
    crawling_progress["completed_rounds"] = completed_rounds
    crawling_progress["status"] = status
    crawling_progress["operation_type"] = operation_type
    crawling_progress["is_running"] = is_running
    if is_running and crawling_progress["start_time"] is None:
        crawling_progress["start_time"] = time.time()
    elif not is_running:
        crawling_progress["start_time"] = None


def _reset_progress():
    """Reset progress to initial state"""
    _update_progress(0, 0, 0, "대기중", "", False)


def _perform_update_with_progress(round_no: int, data_type: str = 'both'):
    """Wrapper for single round update with progress tracking"""
    try:
        operation_name = "특정회차"
        if data_type == "numbers":
            operation_name = "당첨번호만"
        elif data_type == "shops":
            operation_name = "판매점만"

        _update_progress(round_no, 1, 0, f"{round_no}회 수집중", operation_name, True)
        result = svc_perform_update(round_no, data_type)
        _update_progress(round_no, 1, 1, f"{round_no}회 완료", operation_name, False)
        return result
    except Exception as e:
        _update_progress(round_no, 1, 0, f"오류: {str(e)}", operation_name if 'operation_name' in locals() else "특정회차", False)
        raise


def _parse_fixed_numbers(raw: Optional[str]) -> List[int]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace("/", ",").replace(" ", ",").split(",") if p.strip()]
    result: List[int] = []
    for p in parts:
        try:
            n = int(p)
            if 1 <= n <= 45 and n not in result:
                result.append(n)
        except Exception:
            continue
    return result[:5]


@main_bp.get("/")
def index():
    # 모바일 기기 감지 및 리다이렉트
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_index'))

    latest = Draw.query.order_by(Draw.round.desc()).first()
    total_rounds = Draw.query.count()

    # Calculate next draw info
    next_round = latest.round + 1 if latest else 1
    from datetime import datetime, timedelta
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and today.hour >= 21:  # After Saturday 9PM
        days_until_saturday = 7
    next_draw_date = today + timedelta(days=days_until_saturday)
    next_draw_date = next_draw_date.replace(hour=20, minute=45, second=0, microsecond=0)

    # Get user statistics (if authenticated)
    user_stats = {
        'draft_count': 0,
        'pending_count': 0,
        'recent_wins': [],
        'recent_purchases': []
    }

    if current_user.is_authenticated:
        # Draft purchases (장바구니)
        user_stats['draft_count'] = Purchase.query.filter_by(
            user_id=current_user.id,
            status='DRAFT'
        ).count()

        # Pending results (아직 추첨되지 않은 구매)
        user_stats['pending_count'] = Purchase.query.filter(
            Purchase.user_id == current_user.id,
            Purchase.purchase_round >= next_round,
            Purchase.status.in_(['DRAFT', 'PURCHASED'])
        ).count()

        # Recent wins (최근 당첨 내역 - 5등 이상)
        user_stats['recent_wins'] = Purchase.query.filter(
            Purchase.user_id == current_user.id,
            Purchase.winning_rank.isnot(None),
            Purchase.winning_rank <= 5
        ).order_by(Purchase.purchase_date.desc()).limit(3).all()

        # Recent purchases (최근 구매/등록 3건)
        user_stats['recent_purchases'] = Purchase.query.filter_by(
            user_id=current_user.id
        ).order_by(Purchase.purchase_date.desc()).limit(3).all()

    # Get latest round's winning shops (rank 1 only for main page)
    shops_rank1 = []
    if latest:
        shops_rank1 = (
            WinningShop.query.filter_by(round=latest.round, rank=1)
            .order_by(WinningShop.sequence.asc().nullsfirst())
            .limit(5)  # Limit to 5 for dashboard
            .all()
        )

    return render_template(
        "index.html",
        title="로또 대시보드",
        latest=latest,
        total_rounds=total_rounds,
        shops_rank1=shops_rank1,
        next_round=next_round,
        next_draw_date=next_draw_date,
        user_stats=user_stats,
    )


@main_bp.get("/mobile")
def mobile_index():
    """모바일 전용 대시보드"""
    latest = Draw.query.order_by(Draw.round.desc()).first()
    total_rounds = Draw.query.count()

    # Get latest round's winning shops (rank 1 only for main page)
    shops_rank1 = []
    if latest:
        shops_rank1 = (
            WinningShop.query.filter_by(round=latest.round, rank=1)
            .order_by(WinningShop.sequence.asc().nullsfirst())
            .all()
        )

    return render_template(
        "mobile/index.html",
        title="모바일 로또 대시보드",
        latest=latest,
        total_rounds=total_rounds,
        shops_rank1=shops_rank1,
    )


@main_bp.get("/mobile/strategy")
@login_required
def mobile_strategy():
    """모바일 전용 전략분석"""
    draws = Draw.query.order_by(Draw.round.desc()).limit(10).all()
    total_draws = Draw.query.count()
    all_draws = Draw.query.order_by(Draw.round.desc()).all()

    # AI 추천
    recommendations = []
    recommendation_reasons = []
    try:
        rec_data = get_persistent_recommendations(all_draws, current_user.id)
        if rec_data:
            recommendations, recommendation_reasons = rec_data
        else:
            # 기본 추천 생성 (안전한 방식)
            try:
                history = []
                for d in all_draws[:100]:
                    try:
                        numbers = d.numbers_list()
                        if numbers and len(numbers) == 6:
                            history.append(numbers)
                    except:
                        continue

                if history:
                    # Enhanced recommendation with user's winning pattern analysis
                    user_id = current_user.id if current_user.is_authenticated else None
                    rec_result, recommendation_reasons = enhanced_auto_recommend(history, user_id=user_id, count=5)
                    if rec_result:
                        recommendations = rec_result[:5]

                if not recommendations:
                    # 기본 추천
                    recommendations = [[7, 14, 21, 28, 35, 42], [3, 9, 15, 27, 33, 39], [5, 11, 17, 23, 29, 41]]
                    recommendation_reasons = [
                        ["균등 분포 패턴", "7의 배수 활용"],
                        ["저구간 강세", "홀수 위주"],
                        ["전구간 균형", "소수 활용"]
                    ]

            except Exception as e:
                current_app.logger.error(f"Auto recommendation error: {e}")
                recommendations = [[7, 14, 21, 28, 35, 42], [3, 9, 15, 27, 33, 39], [5, 11, 17, 23, 29, 41]]
                recommendation_reasons = [
                    ["균등 분포 패턴", "7의 배수 활용"],
                    ["저구간 강세", "홀수 위주"],
                    ["전구간 균형", "소수 활용"]
                ]
    except Exception as e:
        current_app.logger.error(f"Persistent recommendation error: {e}")
        recommendations = [[7, 14, 21, 28, 35, 42], [3, 9, 15, 27, 33, 39], [5, 11, 17, 23, 29, 41]]
        recommendation_reasons = [
            ["균등 분포 패턴", "7의 배수 활용"],
            ["저구간 강세", "홀수 위주"],
            ["전구간 균형", "소수 활용"]
        ]

    # 구매 내역
    purchases = Purchase.query.filter_by(user_id=current_user.id).order_by(Purchase.purchase_date.desc()).limit(10).all()

    # 통계
    total_purchases = Purchase.query.filter_by(user_id=current_user.id).count()
    total_spent = sum(p.cost or 1000 for p in purchases) if purchases else 0
    total_winnings = sum(p.winning_amount or 0 for p in purchases) if purchases else 0
    win_rate = (len([p for p in purchases if p.winning_amount and p.winning_amount > 0]) / total_purchases * 100) if total_purchases > 0 else 0

    # 번호 분석 데이터 추가 (모바일용 - 최근 50회)
    analysis_limit = 50
    most_frequent = get_most_frequent_numbers(5, analysis_limit)
    least_frequent = get_least_frequent_numbers(5, analysis_limit)
    patterns = analyze_patterns(analysis_limit)
    combinations = get_number_combinations(10, analysis_limit)

    # Get latest draw for next round calculation
    latest_draw = Draw.query.order_by(Draw.round.desc()).first()
    next_round = latest_draw.round + 1 if latest_draw else 1

    return render_template(
        "mobile/strategy.html",
        title="모바일 전략분석",
        draws=draws,
        total_draws=total_draws,
        recommendations=recommendations,
        purchases=purchases,
        total_purchases=total_purchases,
        total_spent=total_spent,
        total_winnings=total_winnings,
        win_rate=round(win_rate, 1),
        # 번호 분석 데이터
        most_frequent=most_frequent,
        least_frequent=least_frequent,
        patterns=patterns,
        combinations=combinations,
        analysis_limit=analysis_limit,
        # 장바구니 기능을 위한 next_round
        next_round=next_round,
    )


@main_bp.get("/mobile/purchases")
@login_required
def mobile_purchases():
    """모바일 전용 구매내역"""
    page = int(request.args.get('page', '1'))
    per_page = 10

    purchases = Purchase.query.filter_by(user_id=current_user.id).order_by(Purchase.purchase_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # 통계 계산
    all_purchases = Purchase.query.filter_by(user_id=current_user.id).all()
    total_purchases = len(all_purchases)
    total_spent = sum(p.cost or 1000 for p in all_purchases)
    total_winnings = sum(p.winning_amount or 0 for p in all_purchases)
    profit_rate = round(((total_winnings - total_spent) / total_spent * 100) if total_spent > 0 else 0, 1)

    # 현재 회차
    latest_draw = Draw.query.order_by(Draw.round.desc()).first()
    current_round = latest_draw.round if latest_draw else 0

    return render_template(
        "mobile/purchases.html",
        title="모바일 구매내역",
        purchases=purchases.items,
        pagination=purchases,
        total_purchases=total_purchases,
        total_spent=total_spent,
        total_winnings=total_winnings,
        profit_rate=profit_rate,
        current_round=current_round
    )


@main_bp.get("/mobile/info")
@login_required
def mobile_info():
    """모바일 전용 정보조회"""
    latest = Draw.query.order_by(Draw.round.desc()).first()
    recent_draws = Draw.query.order_by(Draw.round.desc()).limit(10).all()
    total_rounds = Draw.query.count()

    # 당첨점 통계
    total_shops_1 = WinningShop.query.filter_by(rank=1).count()
    total_shops_2 = WinningShop.query.filter_by(rank=2).count()

    return render_template(
        "mobile/info.html",
        title="모바일 정보조회",
        latest=latest,
        recent_draws=recent_draws,
        total_rounds=total_rounds,
        total_shops_1=total_shops_1,
        total_shops_2=total_shops_2
    )


@main_bp.get("/mobile/crawling")
@login_required
def mobile_crawling():
    """모바일 전용 데이터수집 (최적화)"""
    # 최소 쿼리만 실행
    latest = Draw.query.order_by(Draw.round.desc()).first()

    return render_template(
        "mobile/crawling.html",
        title="모바일 데이터수집",
        latest=latest,
        total_rounds=0  # AJAX로 로드
    )


@main_bp.get("/mobile/buy")
@login_required
def mobile_buy():
    """모바일 구매관리 페이지"""
    # Get latest draw for round calculation
    latest_draw = Draw.query.order_by(Draw.round.desc()).first()
    next_round = latest_draw.round + 1 if latest_draw else 1

    # Get selected round from query params
    selected_round_str = request.args.get('round', str(next_round))
    try:
        selected_round = int(selected_round_str)
    except ValueError:
        selected_round = next_round

    # Calculate draw date info for selected round
    from datetime import datetime, timedelta
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and today.hour >= 21:
        days_until_saturday = 7

    draw_date = today + timedelta(days=days_until_saturday + (selected_round - next_round) * 7)
    draw_date = draw_date.replace(hour=20, minute=45, second=0, microsecond=0)

    # Calculate D-day
    days_diff = (draw_date.date() - today.date()).days
    if days_diff == 0:
        dday = "오늘"
    elif days_diff == 1:
        dday = "내일"
    else:
        dday = f"D-{days_diff}"

    draw_info = {
        'date': draw_date.strftime('%Y-%m-%d'),
        'day': ['월', '화', '수', '목', '금', '토', '일'][draw_date.weekday()],
        'dday': dday
    }

    # Get user's draft purchases
    draft_purchases = Purchase.query.filter_by(
        user_id=current_user.id,
        status='DRAFT'
    ).order_by(Purchase.purchase_date.desc()).all()

    return render_template(
        "mobile/buy.html",
        title="모바일 구매관리",
        selected_round=selected_round,
        draw_info=draw_info,
        draft_purchases=draft_purchases
    )


def _perform_update(round_no: int) -> None:
    svc_perform_update(round_no)


@main_bp.post("/update/<int:round_no>")
@login_required
def update_round(round_no: int):
    try:
        res = svc_perform_update(round_no)
        return {"status": "ok", "round": round_no, **res}
    except Exception as exc:
        return {"status": "error", "round": round_no, "message": str(exc)}, 400


def _run_single_update_background(round_no: int, app, data_type: str = 'both'):
    """Run single round update in background with progress tracking"""
    try:
        with app.app_context():
            _perform_update_with_progress(round_no, data_type)
    except Exception as e:
        print(f"Background update failed: {e}")


def _run_range_update_background(start_round: int, end_round: int, operation_type: str, app, data_type: str = 'both'):
    """Run range update in background with progress tracking"""
    try:
        with app.app_context():
            total_rounds = end_round - start_round + 1
            _update_progress(start_round, total_rounds, 0, "시작 중", operation_type, True)

            for i, round_no in enumerate(range(start_round, end_round + 1)):
                _update_progress(round_no, total_rounds, i, f"{round_no}회 수집중", operation_type, True)
                svc_perform_update(round_no, data_type)
                _update_progress(round_no, total_rounds, i + 1, f"{round_no}회 완료", operation_type, True)
                time.sleep(0.1)  # Small delay to prevent overwhelming the server

            _update_progress(end_round, total_rounds, total_rounds, "모든 회차 완료", operation_type, False)
    except Exception as e:
        _update_progress(0, total_rounds if 'total_rounds' in locals() else 0, 0, f"오류: {str(e)}", operation_type, False)
        print(f"Background range update failed: {e}")


def _run_missing_update_background(app):
    """Run missing rounds update in background with progress tracking"""
    try:
        with app.app_context():
            _update_progress(0, 0, 0, "누락 회차 확인중", "누락회차", True)

            # Get missing rounds (this is a simplified version, actual implementation may vary)
            latest_round = get_latest_round()
            if not latest_round:
                _update_progress(0, 0, 0, "최신 회차를 감지할 수 없음", "누락회차", False)
                return

            all_rounds = set(range(1, latest_round + 1))
            existing_rounds = set(draw.round for draw in Draw.query.all())
            missing_rounds = sorted(list(all_rounds - existing_rounds))

            if not missing_rounds:
                _update_progress(0, 0, 0, "누락된 회차 없음", "누락회차", False)
                return

            total_rounds = len(missing_rounds)

            for i, round_no in enumerate(missing_rounds):
                # 중지 플래그 확인
                if crawling_progress.get("should_stop", False):
                    _update_progress(round_no, total_rounds, i, "중지됨", "누락회차", False)
                    crawling_progress["should_stop"] = False  # 플래그 리셋
                    return

                _update_progress(round_no, total_rounds, i, f"{round_no}회 수집중", "누락회차", True)
                svc_perform_update(round_no)
                _update_progress(round_no, total_rounds, i + 1, f"{round_no}회 완료", "누락회차", True)
                time.sleep(0.1)

            _update_progress(missing_rounds[-1] if missing_rounds else 0, total_rounds, total_rounds, "누락 회차 완료", "누락회차", False)
    except Exception as e:
        _update_progress(0, 0, 0, f"오류: {str(e)}", "누락회차", False)
        print(f"Background missing update failed: {e}")


@main_bp.post("/update")
@login_required
def update_round_from_form():
    try:
        round_no = int(request.form.get("round", "").strip())
        data_type = request.form.get("data_type", "both")  # both, numbers, shops
    except Exception:
        return jsonify({"error": "invalid round"}), 400

    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    # Start background update with data type
    threading.Thread(target=_run_single_update_background, args=(round_no, current_app._get_current_object(), data_type), daemon=True).start()

    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-range")
@login_required
def update_range_api():
    try:
        start_round = int(request.form.get("start", "").strip())
        end_round = int(request.form.get("end", "").strip())
        data_type = request.form.get("data_type", "both")
    except Exception:
        return jsonify({"error": "invalid range"}), 400

    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    if start_round > end_round:
        start_round, end_round = end_round, start_round

    # Start background range update
    operation_name = "범위크롤링"
    if data_type == "numbers":
        operation_name = "범위(당첨번호만)"
    elif data_type == "shops":
        operation_name = "범위(판매점만)"

    threading.Thread(target=_run_range_update_background,
                     args=(start_round, end_round, operation_name, current_app._get_current_object(), data_type),
                     daemon=True).start()

    # 요청 헤더로 모바일/API 요청 구분
    if request.headers.get('Content-Type') == 'application/json' or 'mobile' in request.path:
        return jsonify({"success": True, "message": f"범위 업데이트({start_round}~{end_round}회)가 시작되었습니다"})
    else:
        return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-full")
@login_required
def update_full_api():
    """Complete re-crawling from round 1 to latest."""
    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    latest = get_latest_round()
    if not latest:
        return jsonify({"error": "cannot detect latest round"}), 400

    data_type = request.form.get("data_type", "both")
    operation_name = "전체크롤링"
    if data_type == "numbers":
        operation_name = "전체(당첨번호만)"
    elif data_type == "shops":
        operation_name = "전체(판매점만)"

    # Start background update
    threading.Thread(target=_run_range_update_background,
                     args=(1, latest, operation_name, current_app._get_current_object(), data_type),
                     daemon=True).start()

    # 요청 헤더로 모바일/API 요청 구분
    if request.headers.get('Content-Type') == 'application/json' or 'mobile' in request.path:
        return jsonify({"success": True, "message": f"전체 업데이트(1~{latest}회)가 시작되었습니다"})
    else:
        return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-missing")
@login_required
def update_missing_api():
    """Update only missing rounds."""
    if crawling_progress["is_running"]:
        return jsonify({"success": False, "error": "크롤링이 이미 실행중입니다"}), 400

    # Start background update
    threading.Thread(target=_run_missing_update_background, args=(current_app._get_current_object(),), daemon=True).start()

    # 요청 헤더로 모바일/API 요청 구분
    if request.headers.get('Content-Type') == 'application/json' or 'mobile' in request.path:
        return jsonify({"success": True, "message": "누락 회차 업데이트가 시작되었습니다"})
    else:
        return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-latest")
@login_required
def update_latest_api():
    """Update to the latest available round."""
    if crawling_progress["is_running"]:
        return jsonify({"success": False, "error": "크롤링이 이미 실행중입니다"}), 400

    latest = get_latest_round()
    if not latest:
        return jsonify({"success": False, "error": "최신 회차를 감지할 수 없습니다"}), 400

    data_type = request.form.get("data_type", "both")

    # Start background update for just the latest round
    threading.Thread(target=_run_single_update_background,
                     args=(latest, current_app._get_current_object(), data_type),
                     daemon=True).start()

    # 요청 헤더로 모바일/API 요청 구분
    if request.headers.get('Content-Type') == 'application/json' or 'mobile' in request.path:
        return jsonify({"success": True, "message": f"최신 회차({latest}회) 업데이트가 시작되었습니다"})
    else:
        return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-all")
@login_required
def update_all_api():
    latest = get_latest_round()
    if not latest:
        return jsonify({"error": "cannot detect latest round"}), 400
    # Determine current max round in DB
    current = Draw.query.order_by(Draw.round.desc()).first()
    start = (current.round + 1) if current else 1
    if start > latest:
        return jsonify({"status": "ok", "message": "already up to date"})
    stats = svc_update_range(start, latest)
    return jsonify({"status": "ok", **stats})


# APIs
@main_bp.get("/api/draw/<int:round_no>")
def api_draw(round_no: int):
    d = Draw.query.filter_by(round=round_no).first()
    if not d:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "round": d.round,
        "draw_date": d.draw_date.isoformat() if d.draw_date else None,
        "numbers": d.numbers_list(),
        "bonus": d.bonus,
    })


@main_bp.get("/api/shops/<int:round_no>")
def api_shops(round_no: int):
    shops = (
        WinningShop.query.filter_by(round=round_no)
        .order_by(WinningShop.rank.asc(), WinningShop.sequence.asc().nullsfirst())
        .all()
    )
    return jsonify([
        {
            "round": s.round,
            "rank": s.rank,
            "sequence": s.sequence,
            "name": s.name,
            "method": s.method,
            "address": s.address,
            "winners_count": s.winners_count,
        }
        for s in shops
    ])


@main_bp.get("/strategy")
@login_required
def strategy():
    # 모바일 기기 감지 및 리다이렉트
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_strategy'))

    # Get recent draws for display
    draws = Draw.query.order_by(Draw.round.desc()).limit(10).all()
    total_draws = Draw.query.count()

    # Use all data for AI recommendations
    all_draws = Draw.query.order_by(Draw.round.desc()).all()

    # Get persistent recommendations (or create new ones if none exist)
    auto_recs, recommendation_reasons = get_persistent_recommendations(all_draws, current_user.id)

    # Frequency analysis based on all data (no limit = all data)
    most_frequent = get_most_frequent_numbers(10, limit=None)
    least_frequent = get_least_frequent_numbers(10, limit=None)
    top_combinations = get_number_combinations(10, limit=None)

    # 번호 분석 데이터 추가 (전체 데이터 기반)
    patterns = analyze_patterns(limit=None)
    combinations = get_number_combinations(10, limit=None)
    analysis_limit = total_draws  # 전체 회차 수

    # Get latest draw for next round calculation
    latest_draw = Draw.query.order_by(Draw.round.desc()).first()
    next_round = latest_draw.round + 1 if latest_draw else 1

    return render_template(
        "strategy.html",
        title="전략 분석",
        draws=draws,
        auto_recs=auto_recs,
        most_frequent=most_frequent,
        least_frequent=least_frequent,
        top_combinations=top_combinations,
        recommendation_reasons=recommendation_reasons,
        total_draws=total_draws,
        # 번호 분석 데이터
        patterns=patterns,
        combinations=combinations,
        analysis_limit=analysis_limit,
        # 장바구니 기능을 위한 next_round
        next_round=next_round,
    )


@main_bp.get("/buy")
@login_required
def buy():
    """구매관리 페이지 - 통합 번호 입력 허브"""
    # 모바일 기기 감지 및 리다이렉트
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_buy'))

    # Get latest draw for next round calculation
    latest_draw = Draw.query.order_by(Draw.round.desc()).first()
    next_round = latest_draw.round + 1 if latest_draw else 1

    # Calculate draw date (Saturday 8:45 PM)
    # This is a simplified version - you may want to add actual date calculation
    from datetime import datetime, timedelta
    today = datetime.now()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and today.hour >= 21:  # After Saturday 9PM
        days_until_saturday = 7
    next_draw_date = today + timedelta(days=days_until_saturday)
    next_draw_date = next_draw_date.replace(hour=20, minute=45, second=0, microsecond=0)

    # Get frequency analysis for random generation
    most_frequent = get_most_frequent_numbers(15, limit=None)
    least_frequent = get_least_frequent_numbers(15, limit=None)

    # Get user's draft purchases (장바구니)
    draft_purchases = Purchase.query.filter_by(
        user_id=current_user.id,
        status='DRAFT'
    ).order_by(Purchase.purchase_date.desc()).all()

    # Get pre-filled numbers from query params (from strategy page)
    prefilled_numbers = request.args.get('numbers', '')
    prefilled_method = request.args.get('method', 'manual')

    return render_template(
        "buy.html",
        title="구매관리",
        next_round=next_round,
        next_draw_date=next_draw_date,
        most_frequent=most_frequent,
        least_frequent=least_frequent,
        draft_purchases=draft_purchases,
        prefilled_numbers=prefilled_numbers,
        prefilled_method=prefilled_method,
    )


@main_bp.get("/draw-info")
def draw_info():
    try:
        round_no = int(request.args.get("round", "").strip())
    except Exception:
        return redirect(url_for("main.index"))

    draw = Draw.query.filter_by(round=round_no).first()
    if not draw:
        return redirect(url_for("main.index"))

    # Get winning shops for this specific round
    shops_rank1 = (
        WinningShop.query.filter_by(round=round_no, rank=1)
        .order_by(WinningShop.sequence.asc().nullsfirst())
        .all()
    )

    # Get paginated 2nd rank shops
    per_page = 30
    page = int(request.args.get('rank2_page', '1'))
    if page < 1:
        page = 1

    shops_rank2_total = WinningShop.query.filter_by(round=round_no, rank=2).count()
    shops_rank2_total_pages = (shops_rank2_total + per_page - 1) // per_page

    if page > shops_rank2_total_pages and shops_rank2_total_pages > 0:
        page = shops_rank2_total_pages

    offset = (page - 1) * per_page
    shops_rank2 = (
        WinningShop.query.filter_by(round=round_no, rank=2)
        .order_by(WinningShop.sequence.asc().nullsfirst())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # Get total rounds for context
    total_rounds = Draw.query.count()

    return render_template(
        "draw_info.html",
        title=f"{round_no}회 당첨번호",
        draw=draw,
        latest=draw,  # Use current draw as 'latest' for template compatibility
        total_rounds=total_rounds,
        shops_rank1=shops_rank1,
        shops_rank2=shops_rank2,
        shops_rank2_page=page,
        shops_rank2_total=shops_rank2_total,
        shops_rank2_total_pages=shops_rank2_total_pages,
    )


@main_bp.get("/info")
@login_required
def info_page():
    # 모바일 기기 감지 및 리다이렉트
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_info'))

    latest = Draw.query.order_by(Draw.round.desc()).first()
    draws = Draw.query.order_by(Draw.round.desc()).limit(10).all()
    total_rounds = Draw.query.count()

    # Get latest round's winning shops
    shops_rank1 = []
    shops_rank2 = []
    shops_rank2_total = 0
    shops_rank2_total_pages = 0

    if latest:
        shops_rank1 = (
            WinningShop.query.filter_by(round=latest.round, rank=1)
            .order_by(WinningShop.sequence.asc().nullsfirst())
            .all()
        )

        # Get paginated 2nd rank shops
        per_page = 30
        page = int(request.args.get('rank2_page', '1'))
        if page < 1:
            page = 1

        shops_rank2_total = WinningShop.query.filter_by(round=latest.round, rank=2).count()
        shops_rank2_total_pages = (shops_rank2_total + per_page - 1) // per_page

        if page > shops_rank2_total_pages and shops_rank2_total_pages > 0:
            page = shops_rank2_total_pages

        offset = (page - 1) * per_page
        shops_rank2 = (
            WinningShop.query.filter_by(round=latest.round, rank=2)
            .order_by(WinningShop.sequence.asc().nullsfirst())
            .offset(offset)
            .limit(per_page)
            .all()
        )


    return render_template(
        "info.html",
        title="정보조회",
        latest=latest,
        draws=draws,
        total_rounds=total_rounds,
        shops_rank1=shops_rank1,
        shops_rank2=shops_rank2,
        shops_rank2_page=page if latest else 1,
        shops_rank2_total=shops_rank2_total,
        shops_rank2_total_pages=shops_rank2_total_pages,
    )


@main_bp.get("/crawling")
@login_required
def crawling_page():
    # 모바일 기기 감지 및 리다이렉트
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_crawling'))

    # 최소한의 쿼리만 실행 - 나머지는 AJAX로 로드
    latest = Draw.query.order_by(Draw.round.desc()).first()

    return render_template(
        "crawling.html",
        title="데이터 크롤링",
        latest=latest,
        total_rounds=0,  # AJAX로 로드
    )


@main_bp.get("/api/crawling-progress")
def api_crawling_progress():
    """Get current crawling progress status"""
    progress = crawling_progress.copy()

    # Calculate elapsed time if running
    if progress["is_running"] and progress["start_time"]:
        elapsed = time.time() - progress["start_time"]
        progress["elapsed_seconds"] = int(elapsed)

        # Calculate estimated remaining time
        if progress["completed_rounds"] > 0 and progress["total_rounds"] > 0:
            avg_time_per_round = elapsed / progress["completed_rounds"]
            remaining_rounds = progress["total_rounds"] - progress["completed_rounds"]
            progress["estimated_remaining_seconds"] = int(avg_time_per_round * remaining_rounds)
    else:
        progress["elapsed_seconds"] = 0
        progress["estimated_remaining_seconds"] = 0

    return jsonify(progress)


@main_bp.post("/api/stop-crawling")
def api_stop_crawling():
    """Stop current crawling operation"""
    global crawling_progress

    if not crawling_progress["is_running"]:
        return jsonify({
            "success": False,
            "message": "진행 중인 크롤링이 없습니다."
        })

    # 중지 플래그 설정
    crawling_progress["should_stop"] = True
    crawling_progress["status"] = "중지 요청됨..."

    return jsonify({
        "success": True,
        "message": "크롤링 중지 요청이 전송되었습니다."
    })


@main_bp.get("/api/recommend")
@login_required
def api_recommend():
    draws = Draw.query.order_by(Draw.round.desc()).limit(50).all()
    history = [d.numbers_list() for d in draws]
    fixed = _parse_fixed_numbers(request.args.get("fixed"))
    # Enhanced recommendation with user's winning pattern analysis
    user_id = current_user.id if current_user.is_authenticated else None
    auto_recommendations, auto_reasons = enhanced_auto_recommend(history, user_id=user_id, count=3)

    return jsonify({
        "auto": auto_recommendations,
        "auto_reasons": auto_reasons,
        "semi": semi_auto_recommend(fixed_numbers=fixed),
        "fixed": fixed,
    })


# 구매 기록 관련 라우트
@main_bp.post("/purchase")
@login_required
def purchase_lottery():
    """로또 구매 기록"""
    try:
        numbers = request.form.get("numbers", "").strip()
        method = request.form.get("method", "추천").strip()

        # 번호 검증
        number_list = [int(x) for x in numbers.split(",") if x.strip()]
        if len(number_list) != 6:
            return jsonify({"error": "6개의 번호를 입력해주세요"}), 400

        if not all(1 <= n <= 45 for n in number_list):
            return jsonify({"error": "번호는 1~45 사이여야 합니다"}), 400

        if len(set(number_list)) != 6:
            return jsonify({"error": "중복된 번호는 선택할 수 없습니다"}), 400

        # 다음 회차 계산 (현재 최대 회차 + 1)
        latest_draw = Draw.query.order_by(Draw.round.desc()).first()
        purchase_round = (latest_draw.round + 1) if latest_draw else 1

        # 정렬된 번호
        numbers_string = ",".join(map(str, sorted(number_list)))

        # 중복 구매 체크 (현재 사용자만)
        existing_purchase = Purchase.query.filter_by(
            user_id=current_user.id,
            purchase_round=purchase_round,
            numbers=numbers_string
        ).first()

        if existing_purchase:
            return jsonify({
                "success": False,
                "error": f"{purchase_round}회차에 동일한 번호가 이미 구매되어 있습니다"
            })

        # 구매 기록 저장
        purchase = Purchase(
            user_id=current_user.id,
            purchase_round=purchase_round,
            numbers=numbers_string,
            purchase_method=method
        )

        db.session.add(purchase)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{purchase_round}회 구매가 기록되었습니다",
            "purchase_id": purchase.id,
            "purchase_round": purchase_round,
            "numbers": number_list
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@main_bp.get("/purchases")
@login_required
def purchase_history():
    """구매 이력 페이지"""
    from collections import defaultdict
    from sqlalchemy.orm import joinedload

    # 모바일 기기 감지 및 리다이렉트
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_purchases'))

    page = int(request.args.get('page', '1'))
    per_page = 20
    view_mode = request.args.get('view', 'list')  # 'list' 또는 'grouped'

    # 사용자 필터 (관리자나 특정 사용자만 모든 기록 조회 가능)
    show_all = request.args.get('show_all', 'false').lower() == 'true'
    user_filter = request.args.get('user_id', '').strip()

    # 기본적으로는 현재 사용자의 기록만 조회 (N+1 방지: user 관계 eager loading)
    query = Purchase.query.options(joinedload(Purchase.user))
    current_user_id = current_user.id

    # 관리자 또는 kingchic 사용자는 모든 기록 조회 가능
    if current_user.username in ['kingchic', 'admin'] or hasattr(current_user, 'is_admin') and current_user.is_admin:
        if show_all:
            # 모든 사용자의 기록 조회
            if user_filter and user_filter.isdigit():
                query = query.filter_by(user_id=int(user_filter))
                current_user_id = int(user_filter)
            # show_all=True이고 user_filter가 없으면 모든 사용자 기록
        else:
            # show_all=False이면 현재 사용자 기록만
            query = query.filter_by(user_id=current_user.id)
    else:
        # 일반 사용자는 자신의 기록만
        query = query.filter_by(user_id=current_user.id)

    # 회차별 그룹화 모드
    grouped_purchases = None
    if view_mode == 'grouped':
        # 페이지네이션 없이 모든 데이터 가져오기
        all_purchases = query.order_by(Purchase.purchase_round.desc(), Purchase.purchase_date.desc()).all()

        # 회차별로 그룹화
        grouped_purchases = defaultdict(list)
        for purchase in all_purchases:
            grouped_purchases[purchase.purchase_round].append(purchase)

        # 회차 목록 정렬 (최신 회차 우선)
        grouped_purchases = dict(sorted(grouped_purchases.items(), key=lambda x: x[0], reverse=True))

        # 페이지네이션을 위한 회차 분할
        rounds = list(grouped_purchases.keys())
        total_rounds = len(rounds)
        start_idx = (page - 1) * 5  # 한 페이지에 5개 회차씩
        end_idx = start_idx + 5
        page_rounds = rounds[start_idx:end_idx]

        # 해당 페이지의 회차만 필터링
        grouped_purchases = {round_num: grouped_purchases[round_num] for round_num in page_rounds}

        # 페이지네이션 객체 생성 (회차 단위)
        class GroupedPagination:
            def __init__(self, page, per_page, total):
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page
                self.has_prev = page > 1
                self.has_next = page < self.pages
                self.prev_num = page - 1 if self.has_prev else None
                self.next_num = page + 1 if self.has_next else None
                self.items = []

        purchases = GroupedPagination(page, 5, total_rounds)
    else:
        # 기존 리스트 모드
        purchases = query.order_by(Purchase.purchase_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    # 통계는 조회된 사용자 기준으로 계산
    stats = get_purchase_statistics(current_user_id)

    # 사용자 목록 (관리자용)
    all_users = []
    if current_user.username in ['kingchic', 'admin'] or hasattr(current_user, 'is_admin') and current_user.is_admin:
        all_users = User.query.all()

    return render_template(
        "purchases.html",
        title="구매 이력",
        purchases=purchases,
        grouped_purchases=grouped_purchases,
        view_mode=view_mode,
        stats=stats,
        show_all=show_all,
        user_filter=user_filter,
        all_users=all_users,
        is_admin=(current_user.username in ['kingchic', 'admin'] or hasattr(current_user, 'is_admin') and current_user.is_admin)
    )


@main_bp.post("/check-results")
def check_results():
    """당첨 결과 확인"""
    try:
        results = check_all_pending_results()
        return jsonify({
            "success": True,
            "message": f"{results['total_updated']}건의 결과가 업데이트되었습니다",
            "total_updated": results['total_updated'],
            "updated_rounds": results['updated_rounds']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@main_bp.post("/check-round-result/<int:round_no>")
def check_round_result(round_no: int):
    """특정 회차 결과 확인"""
    try:
        updated = update_purchase_results(round_no)
        if updated == 0:
            return jsonify({
                "success": False,
                "message": f"{round_no}회 당첨번호가 없거나 확인할 구매 기록이 없습니다"
            })

        return jsonify({
            "success": True,
            "message": f"{round_no}회 {updated}건의 결과가 업데이트되었습니다",
            "updated_count": updated
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@main_bp.get("/api/purchase-stats")
@login_required
def api_purchase_stats():
    """구매 통계 API"""
    return jsonify(get_purchase_statistics(current_user.id))


@main_bp.get("/api/check-new-draw")
@login_required
def api_check_new_draw():
    """새로운 추첨 회차가 있는지 확인 (추첨 시간 고려)"""
    try:
        from datetime import datetime, time, timedelta

        # 현재 DB의 최신 회차
        latest_draw = Draw.query.order_by(Draw.round.desc()).first()
        current_round = latest_draw.round if latest_draw else 0

        # 공식 사이트의 최신 회차
        latest_available = get_latest_round()

        if not latest_available:
            return jsonify({
                "has_new_draw": False,
                "message": "최신 회차 정보를 가져올 수 없습니다"
            })

        # 한국 시간 기준으로 계산 (KST)
        now_kst = datetime.now()

        # 로또 추첨 시간: 매주 토요일 오후 8시 45분 (KST)
        # 1회차 추첨일: 2002년 12월 7일 (토요일)
        first_draw_date = datetime(2002, 12, 7)
        weeks_since_first = (now_kst - first_draw_date).days // 7

        # 현재 주의 토요일 8시 45분 계산
        days_until_saturday = (5 - now_kst.weekday()) % 7  # 0=월요일, 5=토요일
        if now_kst.weekday() == 5:  # 현재가 토요일이면
            current_saturday = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            current_saturday = now_kst + timedelta(days=days_until_saturday)
            current_saturday = current_saturday.replace(hour=0, minute=0, second=0, microsecond=0)

        draw_time = current_saturday.replace(hour=20, minute=45)  # 오후 8시 45분

        # 현재 시간이 이번 주 추첨 시간을 지났는지 확인
        draw_completed_this_week = now_kst >= draw_time

        # 예상 회차 계산 (1회차는 2002년 12월 7일)
        if draw_completed_this_week:
            expected_round = weeks_since_first + 1
        else:
            expected_round = weeks_since_first

        # DB 회차와 비교
        has_new_by_schedule = expected_round > current_round
        has_new_by_api = latest_available > current_round

        # 다음 추첨 시간 계산
        if draw_completed_this_week:
            next_draw_time = draw_time + timedelta(days=7)  # 다음 주 토요일
        else:
            next_draw_time = draw_time  # 이번 주 토요일

        # 더 정교한 메시지 생성
        if draw_completed_this_week and has_new_by_schedule:
            if has_new_by_api:
                message = f"이번 주 추첨({expected_round}회)이 완료되었고, 새로운 결과가 있습니다"
            else:
                message = f"이번 주 추첨({expected_round}회)이 완료되었지만, 아직 결과가 공개되지 않았을 수 있습니다"
        elif not draw_completed_this_week and has_new_by_api:
            message = f"추첨 전이지만 이전 회차({latest_available}회) 결과를 업데이트할 수 있습니다"
        elif not draw_completed_this_week and not has_new_by_api:
            hours_until_draw = int((draw_time - now_kst).total_seconds() // 3600)
            if hours_until_draw > 0:
                message = f"다음 추첨까지 약 {hours_until_draw}시간 남았습니다 ({draw_time.strftime('%m-%d %H:%M')})"
            else:
                message = f"오늘 {draw_time.strftime('%H:%M')}에 추첨 예정입니다"
        else:
            message = "새로운 회차가 없습니다"

        return jsonify({
            "has_new_draw": has_new_by_api,
            "current_round": current_round,
            "latest_round": latest_available,
            "expected_round": expected_round,
            "draw_completed": draw_completed_this_week,
            "next_draw_time": next_draw_time.strftime("%Y-%m-%d %H:%M"),
            "hours_until_draw": max(0, int((next_draw_time - now_kst).total_seconds() // 3600)),
            "message": message
        })

    except Exception as e:
        return jsonify({
            "has_new_draw": False,
            "error": str(e)
        }), 400


@main_bp.post("/api/update-new-draw")
@login_required
def api_update_new_draw():
    """새로운 회차 데이터 업데이트"""
    try:
        data = request.get_json()
        round_no = data.get("round")

        if not round_no:
            return jsonify({"success": False, "message": "회차 번호가 필요합니다"}), 400

        # 해당 회차가 이미 있는지 확인
        existing = Draw.query.filter_by(round=round_no).first()
        if existing:
            return jsonify({
                "success": False,
                "message": f"{round_no}회 데이터가 이미 존재합니다"
            })

        # 데이터 업데이트 수행
        result = svc_perform_update(round_no, 'both')

        if result["status"] in ["updated", "partial"]:
            return jsonify({
                "success": True,
                "message": f"{round_no}회 데이터 업데이트 완료",
                "result": result
            })
        else:
            return jsonify({
                "success": False,
                "message": f"{round_no}회 데이터 업데이트 실패"
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


@main_bp.get("/api/data-stats")
def api_data_stats():
    """기본 데이터 통계 정보 API (최적화 버전)"""
    try:
        import os

        # 단일 쿼리로 모든 카운트 가져오기 (최적화)
        stats_query = db.session.query(
            db.func.count(db.func.distinct(Draw.id)).label('draws_count'),
            db.func.max(Draw.round).label('max_round')
        ).first()

        draws_count = stats_query.draws_count or 0
        max_db_round = stats_query.max_round or 0

        # 빠른 통계 - 나머지는 별도 쿼리
        shops_count = WinningShop.query.count()
        purchases_count = Purchase.query.count()
        users_count = User.query.count()

        # 데이터베이스 파일 크기 (캐싱 가능)
        db_path = os.path.join(current_app.instance_path, 'lotto.db')
        db_size_bytes = 0
        db_size_human = "0 MB"

        if os.path.exists(db_path):
            db_size_bytes = os.path.getsize(db_path)
            if db_size_bytes < 1024:
                db_size_human = f"{db_size_bytes} B"
            elif db_size_bytes < 1024 * 1024:
                db_size_human = f"{db_size_bytes / 1024:.2f} KB"
            elif db_size_bytes < 1024 * 1024 * 1024:
                db_size_human = f"{db_size_bytes / (1024 * 1024):.2f} MB"
            else:
                db_size_human = f"{db_size_bytes / (1024 * 1024 * 1024):.2f} GB"

        # 빠른 응답 - 외부 API 호출 없이 DB 기반 통계만 반환
        # 누락 회차는 사용자가 Detail 버튼 클릭 시 로드
        completion_rate = 100.0 if max_db_round > 0 else 0

        return jsonify({
            "missing_count": "?",  # Detail에서 로드
            "completion_rate": completion_rate,
            "total_rounds": draws_count,
            "latest_round": max_db_round,
            "db_size": db_size_human,
            "db_size_bytes": db_size_bytes,
            "table_stats": {
                "draws": draws_count,
                "shops": shops_count,
                "purchases": purchases_count,
                "users": users_count
            },
            "fast_mode": True  # 빠른 모드 표시
        })

    except Exception as e:
        current_app.logger.error(f"Error in api_data_stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main_bp.get("/api/data-detail/<tab_type>")
def api_data_detail(tab_type):
    """상세 데이터 정보 API (최적화 버전)"""
    try:
        # 외부 API 호출 없이 DB만 사용 (빠른 응답)
        stats_query = db.session.query(
            db.func.count(db.func.distinct(Draw.id)).label('total_count'),
            db.func.min(Draw.round).label('min_round'),
            db.func.max(Draw.round).label('max_round')
        ).first()

        total_count = stats_query.total_count or 0
        min_round = stats_query.min_round or 1
        max_round = stats_query.max_round or 0

        if max_round == 0:
            return jsonify({"error": "데이터베이스에 데이터가 없습니다"}), 500

        if tab_type == "missing":
            # 단일 쿼리로 누락 회차 계산 (최적화)
            existing_rounds = set(row[0] for row in db.session.query(Draw.round).all())
            all_rounds = set(range(min_round, max_round + 1))
            missing_rounds = sorted(list(all_rounds - existing_rounds))

            return jsonify({
                "rounds": missing_rounds[:100],  # 최대 100개만 반환
                "total_missing": len(missing_rounds),
                "range": {"start": min_round, "end": max_round},
                "has_more": len(missing_rounds) > 100,
                "fast_mode": True
            })

        elif tab_type == "existing":
            # 페이징 적용 (최적화)
            page = int(request.args.get('page', 1))
            per_page = 100
            offset = (page - 1) * per_page

            existing_rounds = [
                row[0] for row in db.session.query(Draw.round)
                .order_by(Draw.round.desc())
                .limit(per_page)
                .offset(offset)
                .all()
            ]

            return jsonify({
                "rounds": existing_rounds,
                "total_existing": total_count,
                "range": {"start": min_round, "end": max_round},
                "page": page,
                "per_page": per_page,
                "has_more": total_count > (page * per_page)
            })

        elif tab_type == "summary":
            # 빠른 요약 정보 (이미 계산된 값 재사용)
            existing_rounds = set(row[0] for row in db.session.query(Draw.round).all())
            all_rounds = set(range(min_round, max_round + 1))
            missing_count = len(all_rounds - existing_rounds)
            completion_rate = round((total_count / (max_round - min_round + 1)) * 100, 1)

            return jsonify({
                "total_existing": total_count,
                "total_missing": missing_count,
                "completion_rate": completion_rate,
                "range": {"start": min_round, "end": max_round},
                "fast_mode": True
            })

        else:
            return jsonify({"error": "잘못된 탭 타입입니다"}), 400

    except Exception as e:
        current_app.logger.error(f"Error in api_data_detail: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main_bp.get("/api/shop-statistics")
def api_shop_statistics():
    """당첨점 통계 분석 API"""
    try:
        # 기본 통계
        total_shops = WinningShop.query.count()
        rank1_shops = WinningShop.query.filter_by(rank=1).count()
        rank2_shops = WinningShop.query.filter_by(rank=2).count()

        # 지역별 통계 (주소에서 시/도 추출)
        location_stats = db.session.query(
            db.func.substr(WinningShop.address, 1, db.func.instr(WinningShop.address, ' ') - 1).label('region'),
            db.func.count().label('count')
        ).filter(
            WinningShop.address.isnot(None),
            WinningShop.address != ''
        ).group_by('region').order_by(db.func.count().desc()).limit(10).all()

        # 상위 당첨 판매점 (여러번 당첨된 곳)
        top_shops = db.session.query(
            WinningShop.name,
            WinningShop.address,
            db.func.count().label('win_count')
        ).filter(
            WinningShop.rank == 1,
            WinningShop.name.isnot(None)
        ).group_by(WinningShop.name, WinningShop.address).having(
            db.func.count() > 1
        ).order_by(db.func.count().desc()).limit(20).all()

        return jsonify({
            "total_stats": {
                "total_shops": total_shops,
                "rank1_shops": rank1_shops,
                "rank2_shops": rank2_shops
            },
            "location_stats": [
                {"region": region or "알 수 없음", "count": count}
                for region, count in location_stats
            ],
            "top_shops": [
                {
                    "name": shop.name,
                    "address": shop.address,
                    "win_count": shop.win_count
                }
                for shop in top_shops
            ]
        })

    except Exception as e:
        current_app.logger.error(f"Error in api_shop_statistics: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main_bp.get("/api/recommendation-insights")
@login_required
def api_recommendation_insights():
    """사용자 추천 개선 인사이트 API"""
    try:
        from app.services.recommender import generate_recommendation_insights

        insights_data = generate_recommendation_insights(current_user.id)

        return jsonify({
            "success": True,
            "data": insights_data
        })

    except Exception as e:
        current_app.logger.error(f"Error in api_recommendation_insights: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main_bp.get("/api/user-statistics")
@login_required
def api_user_statistics():
    """사용자 구매 패턴 분석 API"""
    try:
        user_id = current_user.id

        # 기본 통계
        total_purchases = Purchase.query.filter_by(
            user_id=user_id,
            status='PURCHASED'
        ).count()

        total_drafts = Purchase.query.filter_by(
            user_id=user_id,
            status='DRAFT'
        ).count()

        # 입력 방식별 통계
        source_stats = db.session.query(
            Purchase.source,
            db.func.count().label('count')
        ).filter(
            Purchase.user_id == user_id,
            Purchase.status == 'PURCHASED'
        ).group_by(Purchase.source).all()

        source_distribution = {}
        for source, count in source_stats:
            source_name = {
                'ai': 'AI 추천',
                'manual': '수동 입력',
                'random': '랜덤 생성',
                'qr': 'QR 스캔',
                None: '기타'
            }.get(source, source or '기타')
            source_distribution[source_name] = count

        # 자주 선택한 번호 (전체 구매 내역에서 추출)
        purchases = Purchase.query.filter_by(
            user_id=user_id,
            status='PURCHASED'
        ).all()

        number_frequency = {}
        for purchase in purchases:
            numbers = purchase.numbers_list()
            for num in numbers:
                number_frequency[num] = number_frequency.get(num, 0) + 1

        # 상위 10개 번호
        top_numbers = sorted(
            number_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # 당첨 통계
        wins_by_rank = db.session.query(
            Purchase.winning_rank,
            db.func.count().label('count')
        ).filter(
            Purchase.user_id == user_id,
            Purchase.winning_rank.isnot(None)
        ).group_by(Purchase.winning_rank).all()

        winning_stats = {}
        total_wins = 0
        for rank, count in wins_by_rank:
            winning_stats[f'{rank}등'] = count
            total_wins += count

        # 회차별 구매 빈도
        round_frequency = db.session.query(
            db.func.count().label('count')
        ).filter(
            Purchase.user_id == user_id,
            Purchase.status == 'PURCHASED'
        ).group_by(Purchase.purchase_round).all()

        avg_purchases_per_round = (
            sum(f[0] for f in round_frequency) / len(round_frequency)
            if round_frequency else 0
        )

        # 전체 사용자 평균 통계 (비교용)
        all_users_purchases = db.session.query(
            db.func.count(Purchase.id).label('total'),
            db.func.count(db.func.distinct(Purchase.user_id)).label('user_count')
        ).filter(
            Purchase.status == 'PURCHASED'
        ).first()

        avg_purchases_all_users = (
            all_users_purchases.total / all_users_purchases.user_count
            if all_users_purchases.user_count > 0 else 0
        )

        all_users_wins = db.session.query(
            db.func.count().label('wins')
        ).filter(
            Purchase.status == 'PURCHASED',
            Purchase.winning_rank.isnot(None)
        ).scalar()

        avg_win_rate_all_users = (
            (all_users_wins / all_users_purchases.total * 100)
            if all_users_purchases.total > 0 else 0
        )

        # 사용자 번호 선택 패턴 분석
        number_patterns = {
            'low_numbers': sum(1 for num, _ in number_frequency.items() if num <= 15),
            'mid_numbers': sum(1 for num, _ in number_frequency.items() if 16 <= num <= 30),
            'high_numbers': sum(1 for num, _ in number_frequency.items() if num >= 31),
            'odd_numbers': sum(count for num, count in number_frequency.items() if num % 2 == 1),
            'even_numbers': sum(count for num, count in number_frequency.items() if num % 2 == 0)
        }

        return jsonify({
            "basic_stats": {
                "total_purchases": total_purchases,
                "total_drafts": total_drafts,
                "total_wins": total_wins,
                "win_rate": round((total_wins / total_purchases * 100), 2) if total_purchases > 0 else 0,
                "avg_purchases_per_round": round(avg_purchases_per_round, 1)
            },
            "comparison": {
                "avg_purchases_all_users": round(avg_purchases_all_users, 1),
                "avg_win_rate_all_users": round(avg_win_rate_all_users, 2),
                "purchases_rank": "평균 이상" if total_purchases > avg_purchases_all_users else "평균 이하",
                "win_rate_rank": "평균 이상" if (total_wins / total_purchases * 100 if total_purchases > 0 else 0) > avg_win_rate_all_users else "평균 이하"
            },
            "source_distribution": source_distribution,
            "favorite_numbers": [
                {"number": num, "count": count}
                for num, count in top_numbers
            ],
            "number_patterns": number_patterns,
            "winning_stats": winning_stats
        })

    except Exception as e:
        current_app.logger.error(f"Error in api_user_statistics: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main_bp.get("/api/shop-search")
def api_shop_search():
    """당첨점 검색 API"""
    try:
        query = request.args.get('q', '').strip()
        rank_filter = request.args.get('rank', 'all')  # 'all', '1', '2'

        if not query or len(query) < 2:
            return jsonify({
                "success": False,
                "error": "검색어는 2글자 이상 입력해주세요"
            }), 400

        # 기본 쿼리 - 판매점명 또는 주소로 검색
        query_filter = db.or_(
            WinningShop.name.like(f'%{query}%'),
            WinningShop.address.like(f'%{query}%')
        )

        # 등수 필터 적용
        if rank_filter == '1':
            shops = WinningShop.query.filter(
                query_filter,
                WinningShop.rank == 1
            ).order_by(
                WinningShop.round.desc()
            ).limit(100).all()
        elif rank_filter == '2':
            shops = WinningShop.query.filter(
                query_filter,
                WinningShop.rank == 2
            ).order_by(
                WinningShop.round.desc()
            ).limit(100).all()
        else:  # 'all'
            shops = WinningShop.query.filter(
                query_filter
            ).order_by(
                WinningShop.round.desc(),
                WinningShop.rank.asc()
            ).limit(100).all()

        # 검색 결과 변환
        results = []
        for shop in shops:
            results.append({
                "round": shop.round,
                "rank": shop.rank,
                "name": shop.name,
                "address": shop.address,
                "method": shop.method,
                "winners_count": shop.winners_count
            })

        # 통계 정보
        total_count = len(results)
        rank1_count = sum(1 for s in results if s['rank'] == 1)
        rank2_count = sum(1 for s in results if s['rank'] == 2)

        return jsonify({
            "success": True,
            "query": query,
            "rank_filter": rank_filter,
            "total_count": total_count,
            "rank1_count": rank1_count,
            "rank2_count": rank2_count,
            "results": results
        })

    except Exception as e:
        current_app.logger.error(f"Error in api_shop_search: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@main_bp.post("/api/refresh-recommendations")
@login_required
def refresh_recommendations_api():
    """AI 추천번호 새로 생성"""
    try:
        all_draws = Draw.query.order_by(Draw.round.desc()).all()
        auto_recs, recommendation_reasons = refresh_recommendations(all_draws, current_user.id)

        return jsonify({
            "success": True,
            "message": "새로운 추천번호가 생성되었습니다",
            "recommendations": auto_recs,
            "reasons": recommendation_reasons
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 400


@main_bp.post("/api/add-manual-numbers")
@login_required
def add_manual_numbers():
    """수동으로 번호 입력"""
    try:
        numbers_str = request.form.get("numbers", "").strip()
        round_str = request.form.get("round", "").strip()

        if not numbers_str:
            return jsonify({
                "success": False,
                "error": "번호를 입력해주세요"
            })

        # 번호 파싱 및 검증
        try:
            numbers = [int(x.strip()) for x in numbers_str.replace(",", " ").split() if x.strip()]

            if len(numbers) != 6:
                return jsonify({
                    "success": False,
                    "error": "정확히 6개의 번호를 입력해주세요"
                })

            if len(set(numbers)) != 6:
                return jsonify({
                    "success": False,
                    "error": "중복된 번호가 있습니다"
                })

            if not all(1 <= num <= 45 for num in numbers):
                return jsonify({
                    "success": False,
                    "error": "번호는 1-45 사이여야 합니다"
                })

        except ValueError:
            return jsonify({
                "success": False,
                "error": "올바른 번호 형식이 아닙니다"
            })

        # 회차 결정
        if round_str:
            try:
                purchase_round = int(round_str)
                if purchase_round < 1:
                    return jsonify({
                        "success": False,
                        "error": "회차는 1 이상이어야 합니다"
                    })
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": "올바른 회차 형식이 아닙니다"
                })
        else:
            # 회차가 입력되지 않았으면 다음 회차로 자동 설정
            latest_draw = Draw.query.order_by(Draw.round.desc()).first()
            purchase_round = latest_draw.round + 1 if latest_draw else 1

        # 정렬된 번호로 저장
        sorted_numbers = sorted(numbers)
        numbers_string = ",".join(map(str, sorted_numbers))

        # 중복 구매 체크 (현재 사용자만)
        existing_purchase = Purchase.query.filter_by(
            user_id=current_user.id,
            purchase_round=purchase_round,
            numbers=numbers_string
        ).first()

        if existing_purchase:
            return jsonify({
                "success": False,
                "error": f"{purchase_round}회차에 동일한 번호가 이미 등록되어 있습니다"
            })

        # Purchase 테이블에 저장
        purchase = Purchase(
            user_id=current_user.id,
            purchase_round=purchase_round,
            numbers=numbers_string,
            purchase_method="수동입력"
        )

        db.session.add(purchase)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{purchase_round}회차 수동 번호가 등록되었습니다: {numbers_string}",
            "purchase_round": purchase_round,
            "numbers": numbers_string
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@main_bp.post("/api/delete-manual-numbers/<int:purchase_id>")
@login_required
def delete_manual_numbers(purchase_id):
    """수동 입력 번호 삭제"""
    try:
        purchase = Purchase.query.filter(
            Purchase.id == purchase_id,
            Purchase.user_id == current_user.id,
            Purchase.purchase_method.in_(["수동입력", "AI추천"])
        ).first()

        if not purchase:
            return jsonify({
                "success": False,
                "error": "해당 번호를 찾을 수 없습니다"
            })

        db.session.delete(purchase)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "번호가 삭제되었습니다"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@main_bp.post("/api/delete-purchase/<int:purchase_id>")
@login_required
def delete_purchase(purchase_id):
    """구매 기록 삭제"""
    try:
        purchase = Purchase.query.filter(
            Purchase.id == purchase_id,
            Purchase.user_id == current_user.id
        ).first()

        if not purchase:
            return jsonify({
                "success": False,
                "error": "해당 구매 기록을 찾을 수 없습니다"
            })

        db.session.delete(purchase)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "구매 기록이 삭제되었습니다"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@main_bp.post("/api/purchases/add")
@login_required
def api_add_purchase():
    """구매 번호 추가 (DRAFT 상태로 저장 - 장바구니)"""
    try:
        # JSON 또는 Form 데이터 모두 지원
        if request.is_json:
            data = request.get_json()
            numbers_str = data.get("numbers", "").strip()
            round_str = str(data.get("round", "")).strip()
            source = data.get("source", "manual")
        else:
            numbers_str = request.form.get("numbers", "").strip()
            round_str = request.form.get("round", "").strip()
            source = request.form.get("source", "manual")  # manual, ai, qr, random

        if not numbers_str:
            return jsonify({
                "success": False,
                "error": "번호를 입력해주세요"
            })

        # 번호 파싱 및 검증
        try:
            numbers = [int(x.strip()) for x in numbers_str.replace(",", " ").split() if x.strip()]

            if len(numbers) != 6:
                return jsonify({
                    "success": False,
                    "error": "정확히 6개의 번호를 입력해주세요"
                })

            if len(set(numbers)) != 6:
                return jsonify({
                    "success": False,
                    "error": "중복된 번호가 있습니다"
                })

            if not all(1 <= num <= 45 for num in numbers):
                return jsonify({
                    "success": False,
                    "error": "번호는 1-45 사이여야 합니다"
                })

        except ValueError:
            return jsonify({
                "success": False,
                "error": "올바른 번호 형식이 아닙니다"
            })

        # 회차 결정
        if round_str:
            try:
                purchase_round = int(round_str)
                if purchase_round < 1:
                    return jsonify({
                        "success": False,
                        "error": "회차는 1 이상이어야 합니다"
                    })
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": "올바른 회차 형식이 아닙니다"
                })
        else:
            # 회차가 입력되지 않았으면 다음 회차로 자동 설정
            latest_draw = Draw.query.order_by(Draw.round.desc()).first()
            purchase_round = latest_draw.round + 1 if latest_draw else 1

        # 정렬된 번호로 저장
        sorted_numbers = sorted(numbers)
        numbers_string = ",".join(map(str, sorted_numbers))

        # 중복 체크 (DRAFT + PURCHASED 모두)
        existing_purchase = Purchase.query.filter_by(
            user_id=current_user.id,
            purchase_round=purchase_round,
            numbers=numbers_string
        ).first()

        if existing_purchase:
            return jsonify({
                "success": False,
                "error": f"{purchase_round}회차에 동일한 번호가 이미 등록되어 있습니다"
            })

        # DRAFT 상태로 저장
        purchase = Purchase(
            user_id=current_user.id,
            purchase_round=purchase_round,
            numbers=numbers_string,
            purchase_method=source,  # legacy field
            source=source,  # new field
            status='DRAFT',
            is_real_purchase=False,
            cost=1000
        )

        db.session.add(purchase)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{purchase_round}회차 번호가 장바구니에 추가되었습니다",
            "purchase_id": purchase.id,
            "purchase_round": purchase_round,
            "numbers": numbers_string
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@main_bp.post("/api/purchases/confirm")
@login_required
def api_confirm_purchases():
    """장바구니의 DRAFT 구매들을 PURCHASED로 확정"""
    try:
        purchase_ids_str = request.form.get("purchase_ids", "").strip()

        if not purchase_ids_str:
            return jsonify({
                "success": False,
                "error": "구매할 번호를 선택해주세요"
            })

        # Parse purchase IDs
        try:
            purchase_ids = [int(x.strip()) for x in purchase_ids_str.split(",") if x.strip()]
        except ValueError:
            return jsonify({
                "success": False,
                "error": "잘못된 구매 ID 형식입니다"
            })

        # Get draft purchases
        draft_purchases = Purchase.query.filter(
            Purchase.id.in_(purchase_ids),
            Purchase.user_id == current_user.id,
            Purchase.status == 'DRAFT'
        ).all()

        if not draft_purchases:
            return jsonify({
                "success": False,
                "error": "선택한 번호를 찾을 수 없습니다"
            })

        # Update status to PURCHASED
        for purchase in draft_purchases:
            purchase.status = 'PURCHASED'
            purchase.is_real_purchase = True

        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{len(draft_purchases)}개 번호가 구매 확정되었습니다",
            "confirmed_count": len(draft_purchases)
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@main_bp.delete("/api/purchases/draft/<int:purchase_id>")
@main_bp.post("/api/purchases/draft/<int:purchase_id>/delete")
@login_required
def api_delete_draft_purchase(purchase_id):
    """장바구니(DRAFT) 구매 삭제"""
    try:
        purchase = Purchase.query.filter(
            Purchase.id == purchase_id,
            Purchase.user_id == current_user.id,
            Purchase.status == 'DRAFT'
        ).first()

        if not purchase:
            return jsonify({
                "success": False,
                "error": "해당 번호를 찾을 수 없습니다"
            })

        db.session.delete(purchase)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "번호가 삭제되었습니다"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@main_bp.route("/api/purchases/draft-count", methods=["GET"])
@login_required
def api_draft_count():
    """장바구니(DRAFT) 개수 조회"""
    try:
        count = Purchase.query.filter(
            Purchase.user_id == current_user.id,
            Purchase.status == 'DRAFT'
        ).count()

        return jsonify({
            "success": True,
            "count": count
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    """로그인 페이지"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('사용자명과 비밀번호를 모두 입력해주세요.')
            return redirect(url_for('main.login'))

        user = User.query.filter_by(username=username).first()

        if user:
            # Check if account is locked
            if user.is_account_locked():
                flash('계정이 일시적으로 잠겨있습니다. 15분 후에 다시 시도해주세요.')
                return redirect(url_for('main.login'))

            if user.check_password(password) and user.is_active:
                user.reset_failed_login()
                db.session.commit()
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('main.index'))
            else:
                user.increment_failed_login()
                db.session.commit()

                remaining_attempts = 5 - user.failed_login_attempts
                if remaining_attempts > 0:
                    flash(f'사용자명 또는 비밀번호가 올바르지 않습니다. ({remaining_attempts}번 더 실패시 계정이 잠깁니다)')
                else:
                    flash('너무 많은 로그인 시도로 인해 계정이 15분간 잠겼습니다.')
                return redirect(url_for('main.login'))
        else:
            # Even if user doesn't exist, add a small delay to prevent user enumeration
            import time
            time.sleep(0.5)
            flash('사용자명 또는 비밀번호가 올바르지 않습니다.')
            return redirect(url_for('main.login'))

    return render_template('login.html')


def validate_password_strength(password):
    """비밀번호 강도 검증"""
    import re

    if len(password) < 8:
        return False, '비밀번호는 최소 8자 이상이어야 합니다.'

    if not re.search(r'[A-Z]', password):
        return False, '비밀번호에 대문자가 포함되어야 합니다.'

    if not re.search(r'[a-z]', password):
        return False, '비밀번호에 소문자가 포함되어야 합니다.'

    if not re.search(r'\d', password):
        return False, '비밀번호에 숫자가 포함되어야 합니다.'

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"\\|,.<>\/?]', password):
        return False, '비밀번호에 특수문자가 포함되어야 합니다.'

    return True, '강력한 비밀번호입니다.'


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    """회원가입 페이지"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == "POST":
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')

        if not all([username, email, password, password_confirm]):
            flash('모든 필드를 입력해주세요.')
            return redirect(url_for('main.register'))

        if password != password_confirm:
            flash('비밀번호가 일치하지 않습니다.')
            return redirect(url_for('main.register'))

        # Enhanced password strength validation
        is_strong, message = validate_password_strength(password)
        if not is_strong:
            flash(message)
            return redirect(url_for('main.register'))

        if User.query.filter_by(username=username).first():
            flash('이미 존재하는 사용자명입니다.')
            return redirect(url_for('main.register'))

        if User.query.filter_by(email=email).first():
            flash('이미 존재하는 이메일입니다.')
            return redirect(url_for('main.register'))

        user = User(username=username, email=email)
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            flash('회원가입이 완료되었습니다. 로그인해주세요.')
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            flash('회원가입 중 오류가 발생했습니다.')
            return redirect(url_for('main.register'))

    return render_template('register.html')


@main_bp.route("/logout")
@login_required
def logout():
    """로그아웃"""
    logout_user()
    flash('로그아웃되었습니다.')
    return redirect(url_for('main.login'))


@main_bp.route("/api/check-username", methods=["POST"])
def check_username():
    """사용자명 중복 체크"""
    username = request.form.get('username', '').strip()

    if not username:
        return jsonify({
            'available': False,
            'message': '사용자명을 입력해주세요.'
        })

    if len(username) < 3:
        return jsonify({
            'available': False,
            'message': '사용자명은 최소 3자 이상이어야 합니다.'
        })

    if len(username) > 20:
        return jsonify({
            'available': False,
            'message': '사용자명은 최대 20자까지 가능합니다.'
        })

    # 영문, 숫자, 언더스코어만 허용
    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({
            'available': False,
            'message': '사용자명은 영문, 숫자, 언더스코어(_)만 사용 가능합니다.'
        })

    # 중복 체크
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({
            'available': False,
            'message': '이미 사용중인 사용자명입니다.'
        })

    return jsonify({
        'available': True,
        'message': '사용 가능한 사용자명입니다.'
    })


@main_bp.route("/api/check-password-strength", methods=["POST"])
def check_password_strength():
    """비밀번호 강도 체크"""
    password = request.form.get('password', '')

    if not password:
        return jsonify({
            'strong': False,
            'message': '비밀번호를 입력해주세요.',
            'score': 0
        })

    is_strong, message = validate_password_strength(password)

    # Calculate score based on criteria met
    score = 0
    if len(password) >= 8:
        score += 20
    if any(c.isupper() for c in password):
        score += 20
    if any(c.islower() for c in password):
        score += 20
    if any(c.isdigit() for c in password):
        score += 20
    if any(c in r'!@#$%^&*()_+-=[]{};\'"\|,.<>/?' for c in password):
        score += 20

    return jsonify({
        'strong': is_strong,
        'message': message,
        'score': score
    })


# ==================== ADMIN ROUTES ====================

@main_bp.route("/admin")
@admin_required
def admin_dashboard():
    """관리자 대시보드"""
    # Get basic statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    admin_users = User.query.filter_by(is_admin=True).count()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                         title='관리자 대시보드',
                         total_users=total_users,
                         active_users=active_users,
                         admin_users=admin_users,
                         recent_users=recent_users)


@main_bp.route("/admin/users")
@admin_required
def admin_users():
    """회원 목록 관리"""
    page = int(request.args.get('page', '1'))
    per_page = 20
    search = request.args.get('search', '').strip()

    query = User.query
    if search:
        query = query.filter(
            (User.username.contains(search)) |
            (User.email.contains(search))
        )

    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('admin/users.html',
                         title='회원 관리',
                         users=users,
                         search=search)


@main_bp.route("/admin/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_user_admin(user_id):
    """사용자 관리자 권한 토글"""
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': '자기 자신의 권한은 변경할 수 없습니다.'}), 400

    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin

    try:
        db.session.commit()
        status = '관리자' if user.is_admin else '일반 사용자'
        return jsonify({
            'success': True,
            'message': f'{user.username}님이 {status}로 변경되었습니다.',
            'is_admin': user.is_admin
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': '권한 변경 중 오류가 발생했습니다.'}), 500


@main_bp.route("/admin/users/<int:user_id>/toggle-active", methods=["POST"])
@admin_required
def toggle_user_active(user_id):
    """사용자 활성 상태 토글"""
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': '자기 자신의 계정은 비활성화할 수 없습니다.'}), 400

    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active

    try:
        db.session.commit()
        status = '활성' if user.is_active else '비활성'
        return jsonify({
            'success': True,
            'message': f'{user.username}님의 계정이 {status} 상태로 변경되었습니다.',
            'is_active': user.is_active
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': '상태 변경 중 오류가 발생했습니다.'}), 500


@main_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    """사용자 삭제"""
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': '자기 자신의 계정은 삭제할 수 없습니다.'}), 400

    user = User.query.get_or_404(user_id)
    username = user.username

    try:
        # Delete related records first
        Purchase.query.filter_by(user_id=user_id).delete()
        RecommendationSet.query.filter_by(user_id=user_id).delete()
        PasswordResetToken.query.filter_by(user_id=user_id).delete()

        # Delete user
        db.session.delete(user)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'{username}님의 계정이 삭제되었습니다.'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': '계정 삭제 중 오류가 발생했습니다.'}), 500


@main_bp.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def admin_reset_password(user_id):
    """관리자가 사용자 비밀번호 재설정"""
    user = User.query.get_or_404(user_id)

    # Generate temporary password
    temp_password = secrets.token_urlsafe(12)
    user.set_password(temp_password)

    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'{user.username}님의 비밀번호가 재설정되었습니다.',
            'temp_password': temp_password
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': '비밀번호 재설정 중 오류가 발생했습니다.'}), 500


# ==================== PASSWORD RESET ROUTES ====================

@main_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """비밀번호 찾기"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == "POST":
        email = request.form.get('email', '').strip()

        if not email:
            flash('이메일 주소를 입력해주세요.')
            return redirect(url_for('main.forgot_password'))

        user = User.query.filter_by(email=email).first()

        if user and user.is_active:
            # Generate reset token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry

            # Remove old tokens for this user
            PasswordResetToken.query.filter_by(user_id=user.id).delete()

            # Create new token
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=expires_at
            )

            try:
                db.session.add(reset_token)
                db.session.commit()

                # In a real application, you would send an email here
                # For now, we'll show the reset link on screen
                reset_url = url_for('main.reset_password', token=token, _external=True)
                flash(f'비밀번호 재설정 링크: {reset_url}', 'info')

            except Exception as e:
                db.session.rollback()
                flash('비밀번호 재설정 요청 중 오류가 발생했습니다.')
        else:
            # Don't reveal if email exists or not
            flash('등록된 이메일이면 비밀번호 재설정 링크가 전송되었습니다.', 'success')

        return redirect(url_for('main.login'))

    return render_template('forgot_password.html')


@main_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """비밀번호 재설정"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    reset_token = PasswordResetToken.query.filter_by(token=token).first()

    if not reset_token or not reset_token.is_valid():
        flash('잘못되거나 만료된 비밀번호 재설정 링크입니다.')
        return redirect(url_for('main.forgot_password'))

    if request.method == "POST":
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if not password or not password_confirm:
            flash('모든 필드를 입력해주세요.')
            return redirect(url_for('main.reset_password', token=token))

        if password != password_confirm:
            flash('비밀번호가 일치하지 않습니다.')
            return redirect(url_for('main.reset_password', token=token))

        # Validate password strength
        is_strong, message = validate_password_strength(password)
        if not is_strong:
            flash(message)
            return redirect(url_for('main.reset_password', token=token))

        # Update password
        user = reset_token.user
        user.set_password(password)
        user.reset_failed_login()  # Reset login attempts

        # Mark token as used
        reset_token.used = True

        try:
            db.session.commit()
            flash('비밀번호가 성공적으로 재설정되었습니다. 새 비밀번호로 로그인해주세요.', 'success')
            return redirect(url_for('main.login'))
        except Exception as e:
            db.session.rollback()
            flash('비밀번호 재설정 중 오류가 발생했습니다.')
            return redirect(url_for('main.reset_password', token=token))

    return render_template('reset_password.html', token=token)


@main_bp.get("/api/draw-info/<int:round_no>")
def api_draw_info(round_no: int):
    """특정 회차 당첨번호 및 판매점 정보"""
    try:
        # 페이지 번호 받기 (기본값: 1)
        page = int(request.args.get('page', '1'))
        if page < 1:
            page = 1
        per_page = 30

        # 당첨번호 조회
        draw = Draw.query.filter_by(round=round_no).first()
        if not draw:
            return jsonify({
                "success": False,
                "error": f"{round_no}회 데이터를 찾을 수 없습니다"
            })

        # 당첨 판매점 조회 (1등, 2등 분리)
        shops_rank1 = WinningShop.query.filter_by(round=round_no, rank=1).order_by(WinningShop.sequence.asc().nullsfirst()).all()

        # 2등 당첨점 페이징
        shops_rank2_total = WinningShop.query.filter_by(round=round_no, rank=2).count()
        shops_rank2_total_pages = (shops_rank2_total + per_page - 1) // per_page

        if page > shops_rank2_total_pages and shops_rank2_total_pages > 0:
            page = shops_rank2_total_pages

        offset = (page - 1) * per_page
        shops_rank2 = WinningShop.query.filter_by(round=round_no, rank=2).order_by(WinningShop.sequence.asc().nullsfirst()).offset(offset).limit(per_page).all()

        return jsonify({
            "success": True,
            "draw": {
                "round": draw.round,
                "draw_date": draw.draw_date.strftime('%Y-%m-%d') if draw.draw_date else None,
                "numbers_list": draw.numbers_list(),
                "bonus": draw.bonus,
                # 당첨금액 정보 추가
                "total_sales": draw.total_sales,
                "first_prize_amount": draw.first_prize_amount,
                "first_prize_winners": draw.first_prize_winners,
                "second_prize_amount": draw.second_prize_amount,
                "second_prize_winners": draw.second_prize_winners,
                "third_prize_amount": draw.third_prize_amount,
                "third_prize_winners": draw.third_prize_winners,
                "fourth_prize_amount": draw.fourth_prize_amount,
                "fourth_prize_winners": draw.fourth_prize_winners,
                "fifth_prize_amount": draw.fifth_prize_amount,
                "fifth_prize_winners": draw.fifth_prize_winners,
                "total_tickets_sold": draw.total_tickets_sold
            },
            "shops": {
                "rank1": [{
                    "sequence": shop.sequence,
                    "name": shop.name,
                    "method": shop.method,
                    "address": shop.address,
                    "rank": shop.rank
                } for shop in shops_rank1],
                "rank2": [{
                    "sequence": shop.sequence,
                    "name": shop.name,
                    "address": shop.address,
                    "rank": shop.rank
                } for shop in shops_rank2],
                "rank2_total": shops_rank2_total,
                "rank2_page": page,
                "rank2_total_pages": shops_rank2_total_pages,
                "rank2_per_page": per_page
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"조회 중 오류가 발생했습니다: {str(e)}"
        }), 400


# =================================================================
# QR 로컬 수집기용 API 엔드포인트
# =================================================================

@main_bp.get('/api/health')
@csrf.exempt
def api_health_check():
    """연결 테스트용 헬스 체크"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0"
    })


def validate_purchase_data(data):
    """구매 데이터 검증"""
    errors = []

    # 필수 필드 검증
    required_fields = ['numbers', 'draw_number', 'purchase_date']
    for field in required_fields:
        if field not in data:
            errors.append(f"필수 필드 '{field}'가 누락되었습니다")

    if errors:
        return errors

    # 번호 검증 (6개 번호, 1-45 범위)
    numbers = data.get('numbers', [])
    if not isinstance(numbers, list) or len(numbers) != 6:
        errors.append("번호는 6개여야 합니다")
    else:
        for num in numbers:
            if not isinstance(num, int) or not (1 <= num <= 45):
                errors.append(f"번호 {num}은 1-45 범위여야 합니다")

        # 중복 번호 검증
        if len(set(numbers)) != len(numbers):
            errors.append("중복된 번호가 있습니다")

    # 회차 번호 검증
    draw_number = data.get('draw_number')
    if not isinstance(draw_number, int) or draw_number < 1:
        errors.append("회차 번호는 1 이상의 정수여야 합니다")

    # 신뢰도 점수 검증 (선택적)
    confidence_score = data.get('confidence_score')
    if confidence_score is not None:
        if not isinstance(confidence_score, (int, float)) or not (0 <= confidence_score <= 100):
            errors.append("신뢰도 점수는 0-100 범위여야 합니다")

    # 인식 방법 검증 (선택적)
    recognition_method = data.get('recognition_method')
    if recognition_method is not None and recognition_method != 'QR':
        errors.append("인식 방법은 'QR'이어야 합니다")

    return errors


@main_bp.post('/api/purchases')
@csrf.exempt
def api_upload_purchase():
    """단일 구매 정보 업로드"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON 데이터가 필요합니다"}), 400

        # 데이터 검증
        validation_errors = validate_purchase_data(data)
        if validation_errors:
            return jsonify({"error": "데이터 검증 실패", "details": validation_errors}), 400

        # 구매 날짜 파싱
        purchase_date_str = data.get('purchase_date')
        try:
            purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({"error": "구매 날짜 형식이 잘못되었습니다 (YYYY-MM-DD)"}), 400

        # 번호를 문자열로 변환
        numbers_str = ','.join(map(str, sorted(data['numbers'])))

        # 사용자 결정: 로그인된 사용자가 있으면 그 사용자, 없으면 local_collector 사용
        if current_user.is_authenticated:
            target_user = current_user
        else:
            # 로컬 수집기용 전용 사용자
            target_user = User.query.filter_by(username='local_collector').first()
            if not target_user:
                # 로컬 수집기용 사용자가 없으면 생성
                target_user = User(
                    username='local_collector',
                    email='local_collector@system.local',
                    is_active=True
                )
                target_user.set_password('system_collector_2024!')
                db.session.add(target_user)
                db.session.commit()

        # 중복 검증: 동일한 사용자, 회차, 번호 조합 확인
        existing_purchase = Purchase.query.filter_by(
            user_id=target_user.id,
            purchase_round=data['draw_number'],
            numbers=numbers_str
        ).first()

        if existing_purchase:
            return jsonify({
                "error": "중복된 구매 정보입니다",
                "details": f"회차 {data['draw_number']}에 이미 동일한 번호가 등록되어 있습니다"
            }), 409

        # 회차당 게임 수 제한 없음 (한 용지당 최대 5게임이지만, 용지 수에는 제한 없음)

        # Purchase 객체 생성
        purchase = Purchase(
            user_id=target_user.id,
            purchase_round=data['draw_number'],
            numbers=numbers_str,
            purchase_date=purchase_date,
            recognition_method=data.get('recognition_method'),
            confidence_score=data.get('confidence_score'),
            source=data.get('source', 'local_collector')
        )

        db.session.add(purchase)
        db.session.commit()

        return jsonify({
            "id": purchase.id,
            "status": "created"
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"구매 정보 저장 중 오류가 발생했습니다: {str(e)}"}), 500


@main_bp.post('/api/purchases/batch')
@csrf.exempt
def api_batch_upload_purchases():
    """일괄 구매 정보 업로드"""
    try:
        data = request.get_json()
        if not data or 'purchases' not in data:
            return jsonify({"error": "purchases 배열이 필요합니다"}), 400

        purchases_data = data['purchases']
        if not isinstance(purchases_data, list):
            return jsonify({"error": "purchases는 배열이어야 합니다"}), 400

        success_count = 0
        failed_count = 0
        errors = []

        # 로컬 수집기용 사용자 확인/생성
        collector_user = User.query.filter_by(username='local_collector').first()
        if not collector_user:
            collector_user = User(
                username='local_collector',
                email='local_collector@system.local',
                is_active=True
            )
            collector_user.set_password('system_collector_2024!')
            db.session.add(collector_user)
            db.session.flush()

        for i, purchase_data in enumerate(purchases_data):
            try:
                # 개별 데이터 검증
                validation_errors = validate_purchase_data(purchase_data)
                if validation_errors:
                    failed_count += 1
                    errors.append(f"항목 {i+1}: {'; '.join(validation_errors)}")
                    continue

                # 구매 날짜 파싱
                purchase_date_str = purchase_data.get('purchase_date')
                try:
                    purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d')
                except ValueError:
                    failed_count += 1
                    errors.append(f"항목 {i+1}: 구매 날짜 형식이 잘못되었습니다")
                    continue

                # 번호를 문자열로 변환
                numbers_str = ','.join(map(str, sorted(purchase_data['numbers'])))

                # Purchase 객체 생성
                purchase = Purchase(
                    user_id=collector_user.id,
                    purchase_round=purchase_data['draw_number'],
                    numbers=numbers_str,
                    purchase_date=purchase_date,
                    recognition_method=purchase_data.get('recognition_method'),
                    confidence_score=purchase_data.get('confidence_score'),
                    source=purchase_data.get('source', 'local_collector')
                )

                db.session.add(purchase)
                success_count += 1

            except Exception as e:
                failed_count += 1
                errors.append(f"항목 {i+1}: {str(e)}")

        # 모든 성공한 항목들을 커밋
        if success_count > 0:
            db.session.commit()

        response_data = {
            "count": success_count,
            "failed_count": failed_count
        }

        # 에러가 있으면 에러 정보도 포함
        if errors:
            response_data["errors"] = errors

        # 부분 성공인 경우 206, 완전 성공인 경우 200, 완전 실패인 경우 400
        if failed_count > 0 and success_count > 0:
            return jsonify(response_data), 206  # Partial Content
        elif success_count > 0:
            return jsonify(response_data), 200
        else:
            return jsonify(response_data), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"일괄 업로드 중 오류가 발생했습니다: {str(e)}"}), 500


@main_bp.post('/api/purchases/qr')
@csrf.exempt
@login_required
def api_upload_qr_purchase():
    """Upload purchase data from QR code scan"""
    try:
        current_app.logger.info(f"QR 업로드 요청 수신 - Content-Type: {request.content_type}")
        current_app.logger.info(f"요청 헤더: {dict(request.headers)}")

        data = request.get_json()
        current_app.logger.info(f"수신된 JSON 데이터: {data}")

        if not data:
            current_app.logger.error("JSON 데이터가 없음")
            return jsonify({"error": "JSON 데이터가 필요합니다"}), 400

        qr_url = data.get('qr_url')
        if not qr_url:
            current_app.logger.error("QR URL이 없음")
            return jsonify({"error": "QR URL이 필요합니다"}), 400

        confidence_score = data.get('confidence_score', 95.0)

        # Parse QR code URL
        current_app.logger.info(f"QR URL 파싱 시작: {qr_url}")
        parsed_qr = parse_lotto_qr_url(qr_url)
        current_app.logger.info(f"QR 파싱 결과: {parsed_qr}")

        if not parsed_qr['valid']:
            return jsonify({
                "error": f"QR 코드 파싱 실패: {parsed_qr['error']}"
            }), 400

        # Convert to purchase records
        purchase_records = parse_qr_data_to_purchases(
            parsed_qr,
            current_user.id,
            confidence_score
        )

        if not purchase_records:
            return jsonify({
                "error": "QR 코드에서 유효한 로또 번호를 찾을 수 없습니다"
            }), 400

        # Check for existing purchases
        round_number = parsed_qr['round']
        saved_purchases = []
        duplicates = []

        for record in purchase_records:
            # Check for duplicate
            existing = Purchase.query.filter_by(
                user_id=current_user.id,
                purchase_round=record['purchase_round'],
                numbers=record['numbers']
            ).first()

            if existing:
                duplicates.append({
                    "numbers": record['numbers'],
                    "round": record['purchase_round']
                })
                continue

            # Create new purchase
            purchase = Purchase(
                user_id=record['user_id'],
                purchase_round=record['purchase_round'],
                numbers=record['numbers'],
                purchase_method=record['purchase_method'],
                recognition_method=record['recognition_method'],
                confidence_score=record['confidence_score'],
                source=record['source'],
                result_checked=record['result_checked']
            )

            db.session.add(purchase)
            saved_purchases.append({
                "id": None,  # Will be set after commit
                "numbers": record['numbers'],
                "round": record['purchase_round'],
                "confidence_score": record['confidence_score']
            })

        # Commit changes
        if saved_purchases:
            db.session.commit()

            # Update IDs after commit
            for i, saved in enumerate(saved_purchases):
                saved["id"] = db.session.query(Purchase).filter_by(
                    user_id=current_user.id,
                    purchase_round=saved["round"],
                    numbers=saved["numbers"]
                ).first().id

        return jsonify({
            "message": f"QR 코드에서 {len(saved_purchases)}개 번호 저장 완료",
            "round": round_number,
            "saved_count": len(saved_purchases),
            "duplicate_count": len(duplicates),
            "purchases": saved_purchases,
            "duplicates": duplicates,
            "parsed_games": len(parsed_qr['games'])
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"QR upload error: {e}")
        return jsonify({"error": f"QR 코드 처리 중 오류: {str(e)}"}), 500


@main_bp.post('/api/purchases/text')
@csrf.exempt
@login_required
def api_upload_text_purchase():
    """텍스트에서 구매 데이터 업로드"""
    try:
        from app.services.text_parser import parse_lottery_text
        from datetime import datetime

        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({"error": "텍스트 데이터가 필요합니다"}), 400

        text = data.get('text')

        # 텍스트 파싱
        parse_result = parse_lottery_text(text)

        if not parse_result['success']:
            return jsonify({
                "error": f"텍스트 파싱 실패: {parse_result.get('error', 'Unknown error')}"
            }), 400

        parsed_data = parse_result['data']
        round_number = parsed_data['round']
        games = parsed_data['games']

        # purchase_date를 datetime 객체로 변환
        purchase_date = None
        if parsed_data.get('purchase_date'):
            try:
                purchase_date = datetime.strptime(parsed_data['purchase_date'], '%Y-%m-%d')
            except ValueError:
                pass

        # 각 게임을 Purchase로 저장
        saved_purchases = []
        duplicates = []

        for game in games:
            numbers = ','.join(map(str, game['numbers']))

            # 중복 체크
            existing = Purchase.query.filter_by(
                user_id=current_user.id,
                purchase_round=round_number,
                numbers=numbers
            ).first()

            if existing:
                duplicates.append({
                    "numbers": numbers,
                    "round": round_number,
                    "game_type": game['game_type']
                })
                continue

            # 새 구매 기록 생성
            purchase = Purchase(
                user_id=current_user.id,
                purchase_round=round_number,
                numbers=numbers,
                purchase_method=game['mode'],  # 자동/수동
                purchase_date=purchase_date,
                recognition_method='text_input',
                source='web_text_input',
                result_checked=False
            )

            db.session.add(purchase)
            saved_purchases.append({
                "game_type": game['game_type'],
                "numbers": numbers,
                "mode": game['mode']
            })

        # 커밋
        if saved_purchases:
            db.session.commit()

        return jsonify({
            "success": True,
            "message": f"{len(saved_purchases)}개 게임 저장 완료",
            "data": {
                "round": round_number,
                "purchase_date": parsed_data.get('purchase_date'),
                "draw_date": parsed_data.get('draw_date'),
                "games": games
            },
            "upload_result": {
                "saved": len(saved_purchases),
                "duplicates": len(duplicates)
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Text upload error: {e}")
        return jsonify({"error": f"텍스트 처리 중 오류: {str(e)}"}), 500


@main_bp.get('/api/purchases/sync')
@csrf.exempt
def api_sync_purchases():
    """동기화용 구매 데이터 조회"""
    try:
        # 쿼리 파라미터 처리
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        since_date = request.args.get('since_date')  # YYYY-MM-DD 형식

        # 기본 쿼리
        query = Purchase.query

        # 로컬 수집기 사용자의 데이터만 조회
        collector_user = User.query.filter_by(username='local_collector').first()
        if collector_user:
            query = query.filter(Purchase.user_id == collector_user.id)

        # 날짜 필터링
        if since_date:
            try:
                since_datetime = datetime.strptime(since_date, '%Y-%m-%d')
                query = query.filter(Purchase.purchase_date >= since_datetime)
            except ValueError:
                return jsonify({"error": "since_date 형식이 잘못되었습니다 (YYYY-MM-DD)"}), 400

        # 정렬 및 페이징
        total_count = query.count()
        purchases = query.order_by(Purchase.purchase_date.desc()).offset(offset).limit(limit).all()

        # 응답 데이터 구성
        purchase_list = []
        for purchase in purchases:
            purchase_list.append({
                "id": purchase.id,
                "numbers": purchase.numbers_list(),
                "draw_number": purchase.purchase_round,
                "purchase_date": purchase.purchase_date.strftime('%Y-%m-%d'),
                "recognition_method": purchase.recognition_method,
                "confidence_score": purchase.confidence_score,
                "source": purchase.source,
                "result_checked": purchase.result_checked,
                "winning_rank": purchase.winning_rank,
                "matched_count": purchase.matched_count,
                "created_at": purchase.purchase_date.isoformat() + "Z"
            })

        return jsonify({
            "purchases": purchase_list,
            "total_count": total_count,
            "returned_count": len(purchase_list),
            "offset": offset,
            "limit": limit
        })

    except Exception as e:
        return jsonify({"error": f"데이터 조회 중 오류가 발생했습니다: {str(e)}"}), 500


@main_bp.get('/api/user/info')
@csrf.exempt
def api_get_user_info():
    """현재 로그인된 사용자 정보 반환"""
    if not current_user.is_authenticated:
        return jsonify({"error": "로그인이 필요합니다"}), 401

    return jsonify({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    })



# ======================
# QR 앱 관련 API
# ======================

@main_bp.get("/api/qr-app/version")
@csrf.exempt
def api_qr_app_version():
    """QR 앱 버전 정보 API"""
    return jsonify({
        "version": "1.1.0",
        "release_date": "2025-10-04",
        "download_url": "https://github.com/your-repo/releases/latest",
        "changelog": [
            "✨ 드래그 앤 드롭 지원",
            "✨ 폴더 일괄 처리 기능",
            "✨ 프로그레스 바 추가",
            "✨ 키보드 단축키 지원",
            "✨ 자동 재시도 메커니즘",
            "✨ CSV/JSON 내보내기 기능"
        ],
        "minimum_version": "1.0.0"
    })
