from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app, flash, abort
import re
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
import threading
import time
import secrets
from datetime import timedelta, datetime
from typing import Optional, List

from .extensions import db
from .models import Draw, WinningShop, Purchase, User, PasswordResetToken, RecommendationSet
from .services.lotto_fetcher import fetch_draw, fetch_winning_shops
from .services.updater import (
    perform_update as svc_perform_update,
    update_range as svc_update_range,
    get_latest_round,
    update_missing_rounds,
    update_to_latest
)
from .services.recommender import auto_recommend, semi_auto_recommend
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

    # Get latest round's winning shops (rank 1 only for main page)
    shops_rank1 = []
    if latest:
        shops_rank1 = (
            WinningShop.query.filter_by(round=latest.round, rank=1)
            .order_by(WinningShop.sequence.asc().nullsfirst())
            .all()
        )

    return render_template(
        "index.html",
        title="로또 대시보드",
        latest=latest,
        total_rounds=total_rounds,
        shops_rank1=shops_rank1,
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
        rec_data = get_persistent_recommendations(current_user.id)
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
                    rec_result = auto_recommend(history, count=5)
                    if rec_result:
                        recommendations = rec_result[:5]
                
                if not recommendations:
                    # 기본 추천
                    recommendations = [[7, 14, 21, 28, 35, 42], [3, 9, 15, 27, 33, 39], [5, 11, 17, 23, 29, 41]]
                    
            except Exception as e:
                current_app.logger.error(f"Auto recommendation error: {e}")
                recommendations = [[7, 14, 21, 28, 35, 42], [3, 9, 15, 27, 33, 39], [5, 11, 17, 23, 29, 41]]
    except Exception as e:
        current_app.logger.error(f"Persistent recommendation error: {e}")
        recommendations = [[7, 14, 21, 28, 35, 42], [3, 9, 15, 27, 33, 39], [5, 11, 17, 23, 29, 41]]

    # 구매 내역
    purchases = Purchase.query.filter_by(user_id=current_user.id).order_by(Purchase.purchase_date.desc()).limit(10).all()

    # 통계
    total_purchases = Purchase.query.filter_by(user_id=current_user.id).count()
    total_spent = sum(p.cost or 1000 for p in purchases) if purchases else 0
    total_winnings = sum(p.winning_amount or 0 for p in purchases) if purchases else 0
    win_rate = (len([p for p in purchases if p.winning_amount and p.winning_amount > 0]) / total_purchases * 100) if total_purchases > 0 else 0

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
        win_rate=round(win_rate, 1)
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
    """모바일 전용 데이터수집"""
    latest = Draw.query.order_by(Draw.round.desc()).first()
    total_rounds = Draw.query.count()

    return render_template(
        "mobile/crawling.html",
        title="모바일 데이터수집",
        latest=latest,
        total_rounds=total_rounds
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
            all_rounds = set(range(1, get_latest_round() + 1))
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

    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-missing")
@login_required
def update_missing_api():
    """Update only missing rounds."""
    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    # Start background update
    threading.Thread(target=_run_missing_update_background, args=(current_app._get_current_object(),), daemon=True).start()

    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-latest")
@login_required
def update_latest_api():
    """Update to the latest available round."""
    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    latest = get_latest_round()
    if not latest:
        return jsonify({"error": "cannot detect latest round"}), 400

    data_type = request.form.get("data_type", "both")

    # Start background update for just the latest round
    threading.Thread(target=_run_single_update_background,
                     args=(latest, current_app._get_current_object(), data_type),
                     daemon=True).start()

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

    # Get user's manual numbers with pagination (10개 단위)
    manual_page = int(request.args.get('manual_page', '1'))
    manual_per_page = 20
    manual_numbers = Purchase.query.filter(
        Purchase.user_id == current_user.id,
        Purchase.purchase_method.in_(["수동입력", "AI추천"])
    ).order_by(Purchase.purchase_date.desc()).paginate(
        page=manual_page, per_page=manual_per_page, error_out=False
    )

    # Get current user's purchased numbers for duplicate check (next round)
    latest_draw = Draw.query.order_by(Draw.round.desc()).first()
    next_round = latest_draw.round + 1 if latest_draw else 1
    purchased_numbers = Purchase.query.filter_by(
        user_id=current_user.id,
        purchase_round=next_round
    ).all()
    purchased_numbers_list = [p.numbers for p in purchased_numbers]

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
        manual_numbers=manual_numbers,
        purchased_numbers=purchased_numbers_list,
        next_round=next_round,
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

    return render_template(
        "draw_info.html",
        title=f"{round_no}회 당첨번호",
        draw=draw
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
        per_page = 10
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

    # 번호 분석 데이터 추가 (최근 50회 기준)
    analysis_limit = 50
    most_frequent = get_most_frequent_numbers(10, analysis_limit)
    least_frequent = get_least_frequent_numbers(10, analysis_limit)
    patterns = analyze_patterns(analysis_limit)
    hot_cold = get_hot_cold_analysis(analysis_limit)
    combinations = get_number_combinations(5, analysis_limit)

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
        # 분석 데이터
        most_frequent=most_frequent,
        least_frequent=least_frequent,
        patterns=patterns,
        hot_cold=hot_cold,
        combinations=combinations,
        analysis_limit=analysis_limit,
    )


@main_bp.get("/crawling")
@login_required
def crawling_page():
    # 모바일 기기 감지 및 리다이렉트
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_crawling'))

    latest = Draw.query.order_by(Draw.round.desc()).first()
    total_rounds = Draw.query.count()

    return render_template(
        "crawling.html",
        title="데이터 크롤링",
        latest=latest,
        total_rounds=total_rounds,
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
    return jsonify({
        "auto": auto_recommend(history, count=3),
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
    # 모바일 기기 감지 및 리다이렉트
    if mobile_redirect_check():
        return redirect(url_for('main.mobile_purchases'))

    page = int(request.args.get('page', '1'))
    per_page = 20

    purchases = Purchase.query.filter_by(user_id=current_user.id).order_by(Purchase.purchase_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    stats = get_purchase_statistics(current_user.id)

    return render_template(
        "purchases.html",
        title="구매 이력",
        purchases=purchases,
        stats=stats
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
        # 당첨번호 조회
        draw = Draw.query.filter_by(round=round_no).first()
        if not draw:
            return jsonify({
                "success": False,
                "error": f"{round_no}회 데이터를 찾을 수 없습니다"
            })

        # 당첨 판매점 조회
        shops = WinningShop.query.filter_by(round=round_no).order_by(WinningShop.rank).all()

        return jsonify({
            "success": True,
            "draw": {
                "round": draw.round,
                "draw_date": draw.draw_date.strftime('%Y-%m-%d') if draw.draw_date else None,
                "numbers_list": draw.numbers_list(),
                "bonus": draw.bonus
            },
            "shops": [{
                "name": shop.name,
                "address": shop.address,
                "rank": f"{shop.rank}"
            } for shop in shops]
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"조회 중 오류가 발생했습니다: {str(e)}"
        }), 400
