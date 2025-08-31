from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
import threading
import time
from typing import Optional, List

from .extensions import db
from .models import Draw, WinningShop, Purchase
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
from .services.lottery_checker import (
    check_all_pending_results, get_purchase_statistics,
    get_recent_purchases_with_results, update_purchase_results
)
from .services.recommendation_manager import (
    get_persistent_recommendations, refresh_recommendations
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
        data_type = request.form.get("data_type", "both")  # both, numbers, shops
    except Exception:
        return jsonify({"error": "invalid round"}), 400

    if crawling_progress["is_running"]:
        return jsonify({"error": "크롤링이 이미 실행중입니다"}), 400

    # Start background update with data type
    threading.Thread(target=_run_single_update_background, args=(round_no, current_app._get_current_object(), data_type), daemon=True).start()

    return redirect(url_for("main.crawling_page"))


@main_bp.post("/update-range")
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

    data_type = request.form.get("data_type", "both")

    # Start background update for just the latest round
    threading.Thread(target=_run_single_update_background,
                     args=(latest, current_app._get_current_object(), data_type),
                     daemon=True).start()

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
    draws = Draw.query.order_by(Draw.round.desc()).limit(10).all()
    total_draws = Draw.query.count()

    # Use all data for AI recommendations
    all_draws = Draw.query.order_by(Draw.round.desc()).all()

    # Get persistent recommendations (or create new ones if none exist)
    auto_recs, recommendation_reasons = get_persistent_recommendations(all_draws)

    # Frequency analysis based on all data (no limit = all data)
    most_frequent = get_most_frequent_numbers(10, limit=None)
    least_frequent = get_least_frequent_numbers(10, limit=None)
    top_combinations = get_number_combinations(10, limit=None)

    # Get user's manual numbers from Purchase table (last 10)
    manual_numbers = Purchase.query.filter(
        Purchase.purchase_method.in_(["수동입력", "AI추천"])
    ).order_by(Purchase.purchase_date.desc()).limit(10).all()

    # Get all purchased numbers for duplicate check (next round)
    latest_draw = Draw.query.order_by(Draw.round.desc()).first()
    next_round = latest_draw.round + 1 if latest_draw else 1
    purchased_numbers = Purchase.query.filter_by(purchase_round=next_round).all()
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


# 구매 기록 관련 라우트
@main_bp.post("/purchase")
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

        # 중복 구매 체크
        existing_purchase = Purchase.query.filter_by(
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
def purchase_history():
    """구매 이력 페이지"""
    page = int(request.args.get('page', '1'))
    per_page = 20

    purchases = Purchase.query.order_by(Purchase.purchase_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    stats = get_purchase_statistics()

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
def api_purchase_stats():
    """구매 통계 API"""
    return jsonify(get_purchase_statistics())


@main_bp.get("/api/check-new-draw")
def api_check_new_draw():
    """새로운 추첨 회차가 있는지 확인"""
    try:
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

        has_new = latest_available > current_round

        return jsonify({
            "has_new_draw": has_new,
            "current_round": current_round,
            "latest_round": latest_available,
            "message": f"새로운 회차가 {'있습니다' if has_new else '없습니다'}"
        })

    except Exception as e:
        return jsonify({
            "has_new_draw": False,
            "error": str(e)
        }), 400


@main_bp.post("/api/update-new-draw")
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
def refresh_recommendations_api():
    """AI 추천번호 새로 생성"""
    try:
        all_draws = Draw.query.order_by(Draw.round.desc()).all()
        auto_recs, recommendation_reasons = refresh_recommendations(all_draws)

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

        # 중복 구매 체크
        existing_purchase = Purchase.query.filter_by(
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
def delete_manual_numbers(purchase_id):
    """수동 입력 번호 삭제"""
    try:
        purchase = Purchase.query.filter(
            Purchase.id == purchase_id,
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
def delete_purchase(purchase_id):
    """구매 기록 삭제"""
    try:
        purchase = Purchase.query.get(purchase_id)

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
