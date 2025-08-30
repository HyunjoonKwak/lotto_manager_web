from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
import threading
import time

from .extensions import db
from .models import Draw, WinningShop
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
    get_most_frequent_numbers, get_least_frequent_numbers,
    get_number_combinations, get_recommendation_reasons,
    get_hot_cold_analysis
)


main_bp = Blueprint("main", __name__)

# Progress tracking storage
crawling_progress = {
    "is_running": False,
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


def _perform_update_with_progress(round_no: int):
    """Wrapper for single round update with progress tracking"""
    try:
        _update_progress(round_no, 1, 0, f"{round_no}회 수집중", "특정회차", True)
        result = svc_perform_update(round_no)
        _update_progress(round_no, 1, 1, f"{round_no}회 완료", "특정회차", False)
        return result
    except Exception as e:
        _update_progress(round_no, 1, 0, f"오류: {str(e)}", "특정회차", False)
        raise


def _parse_fixed_numbers(raw: str | None) -> list[int]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace("/", ",").replace(" ", ",").split(",") if p.strip()]
    result: list[int] = []
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


def _perform_update(round_no: int) -> None:
    svc_perform_update(round_no)


@main_bp.post("/update/<int:round_no>")
def update_round(round_no: int):
    try:
        res = svc_perform_update(round_no)
        return {"status": "ok", "round": round_no, **res}
    except Exception as exc:
        return {"status": "error", "round": round_no, "message": str(exc)}, 400


def _run_single_update_background(round_no: int, app):
    """Run single round update in background with progress tracking"""
    try:
        with app.app_context():
            _perform_update_with_progress(round_no)
    except Exception as e:
        print(f"Background update failed: {e}")


def _run_range_update_background(start_round: int, end_round: int, operation_type: str, app):
    """Run range update in background with progress tracking"""
    try:
        with app.app_context():
            total_rounds = end_round - start_round + 1
            _update_progress(start_round, total_rounds, 0, "시작 중", operation_type, True)

            for i, round_no in enumerate(range(start_round, end_round + 1)):
                _update_progress(round_no, total_rounds, i, f"{round_no}회 수집중", operation_type, True)
                svc_perform_update(round_no)
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
                _update_progress(round_no, total_rounds, i, f"{round_no}회 수집중", "누락회차", True)
                svc_perform_update(round_no)
                _update_progress(round_no, total_rounds, i + 1, f"{round_no}회 완료", "누락회차", True)
                time.sleep(0.1)

            _update_progress(missing_rounds[-1] if missing_rounds else 0, total_rounds, total_rounds, "누락 회차 완료", "누락회차", False)
    except Exception as e:
        _update_progress(0, 0, 0, f"오류: {str(e)}", "누락회차", False)
        print(f"Background missing update failed: {e}")


@main_bp.post("/update")
def update_round_from_form():
    try:
        round_no = int(request.form.get("round", "").strip())
    except Exception:
        return jsonify({"error": "invalid round"}), 400

    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    # Start background update
    threading.Thread(target=_run_single_update_background, args=(round_no, current_app._get_current_object()), daemon=True).start()

    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-range")
def update_range_api():
    try:
        start_round = int(request.form.get("start", "").strip())
        end_round = int(request.form.get("end", "").strip())
    except Exception:
        return jsonify({"error": "invalid range"}), 400
    if start_round > end_round:
        start_round, end_round = end_round, start_round
    svc_update_range(start_round, end_round)
    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-full")
def update_full_api():
    """Complete re-crawling from round 1 to latest."""
    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    latest = get_latest_round()
    if not latest:
        return jsonify({"error": "cannot detect latest round"}), 400

    # Start background update
    threading.Thread(target=_run_range_update_background, args=(1, latest, "전체크롤링", current_app._get_current_object()), daemon=True).start()

    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-missing")
def update_missing_api():
    """Update only missing rounds."""
    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    # Start background update
    threading.Thread(target=_run_missing_update_background, args=(current_app._get_current_object(),), daemon=True).start()

    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-latest")
def update_latest_api():
    """Update to the latest available round."""
    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    latest = get_latest_round()
    if not latest:
        return jsonify({"error": "cannot detect latest round"}), 400

    # Start background update for just the latest round
    threading.Thread(target=_run_single_update_background, args=(latest, current_app._get_current_object()), daemon=True).start()

    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-all")
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
def strategy():
    # Get recent draws for display
    draws = Draw.query.order_by(Draw.round.desc()).limit(5).all()
    total_draws = Draw.query.count()

    # Use all data for AI recommendations
    all_draws = Draw.query.order_by(Draw.round.desc()).all()
    history = [d.numbers_list() for d in all_draws]

    # AI recommendations based on all data
    auto = auto_recommend(history, count=5)

    # Frequency analysis based on all data (no limit = all data)
    most_frequent = get_most_frequent_numbers(10, limit=None)
    least_frequent = get_least_frequent_numbers(10, limit=None)
    top_combinations = get_number_combinations(10, limit=None)

    # Generate reasons for recommendations based on all data
    reasons = []
    for rec in auto:
        reasons.append(get_recommendation_reasons(rec, limit=None))

    return render_template(
        "strategy.html",
        title="전략 분석",
        draws=draws,
        auto_recs=auto,
        most_frequent=most_frequent,
        least_frequent=least_frequent,
        top_combinations=top_combinations,
        recommendation_reasons=reasons,
        total_draws=total_draws,
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
def info_page():
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
def crawling_page():
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


@main_bp.get("/api/recommend")
def api_recommend():
    draws = Draw.query.order_by(Draw.round.desc()).limit(50).all()
    history = [d.numbers_list() for d in draws]
    fixed = _parse_fixed_numbers(request.args.get("fixed"))
    return jsonify({
        "auto": auto_recommend(history, count=3),
        "semi": semi_auto_recommend(fixed_numbers=fixed),
        "fixed": fixed,
    })
