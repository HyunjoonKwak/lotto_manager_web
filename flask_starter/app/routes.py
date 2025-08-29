from flask import Blueprint, render_template, request, jsonify, redirect, url_for

from .extensions import db
from .models import Draw, WinningShop
from .services.lotto_fetcher import fetch_draw, fetch_winning_shops
from .services.updater import perform_update as svc_perform_update, update_range as svc_update_range, get_latest_round
from .services.recommender import auto_recommend, semi_auto_recommend


main_bp = Blueprint("main", __name__)


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
    draws = Draw.query.order_by(Draw.round.desc()).limit(20).all()
    total_rounds = Draw.query.count()
    history = [d.numbers_list() for d in draws]
    auto = auto_recommend(history, count=3)
    fixed = _parse_fixed_numbers(request.args.get("fixed"))
    semi = semi_auto_recommend(fixed_numbers=fixed)
    # Determine which round's shops to display (default: latest)
    shops_round = None
    try:
        if request.args.get("shops_round"):
            shops_round = int(request.args.get("shops_round", "").strip())
    except Exception:
        shops_round = None
    if shops_round is None and latest:
        shops_round = latest.round

    shops_rank1 = []
    shops_rank2 = []
    shops_rank2_page = 1
    shops_rank2_per_page = 30
    shops_rank2_total = 0
    shops_rank2_total_pages = 0

    # Get page parameter for 2nd rank shops
    try:
        shops_rank2_page = int(request.args.get('rank2_page', '1'))
        if shops_rank2_page < 1:
            shops_rank2_page = 1
    except (ValueError, TypeError):
        shops_rank2_page = 1

    if shops_round is not None:
        shops_rank1 = (
            WinningShop.query.filter_by(round=shops_round, rank=1)
            .order_by(WinningShop.sequence.asc().nullsfirst())
            .all()
        )

        # Get total count for 2nd rank shops
        shops_rank2_total = WinningShop.query.filter_by(round=shops_round, rank=2).count()
        shops_rank2_total_pages = (shops_rank2_total + shops_rank2_per_page - 1) // shops_rank2_per_page

        # Get paginated 2nd rank shops
        offset = (shops_rank2_page - 1) * shops_rank2_per_page
        shops_rank2 = (
            WinningShop.query.filter_by(round=shops_round, rank=2)
            .order_by(WinningShop.sequence.asc().nullsfirst())
            .offset(offset)
            .limit(shops_rank2_per_page)
            .all()
        )
    return render_template(
        "index.html",
        title="로또 대시보드",
        latest=latest,
        draws=draws,
        total_rounds=total_rounds,
        auto_recs=auto,
        semi_recs=semi,
        shops_rank1=shops_rank1,
        shops_rank2=shops_rank2,
        shops_rank2_page=shops_rank2_page,
        shops_rank2_total=shops_rank2_total,
        shops_rank2_total_pages=shops_rank2_total_pages,
        shops_rank2_per_page=shops_rank2_per_page,
        shops_round=shops_round,
        fixed=fixed,
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


@main_bp.post("/update")
def update_round_from_form():
    try:
        round_no = int(request.form.get("round", "").strip())
    except Exception:
        return jsonify({"error": "invalid round"}), 400
    try:
        svc_perform_update(round_no)
        return redirect(url_for("main.index"))
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


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
    return redirect(url_for("main.index"))


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
