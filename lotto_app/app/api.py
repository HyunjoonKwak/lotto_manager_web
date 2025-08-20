from flask import Blueprint, jsonify, request
from app.models import db, Draw, Recommendation, RecScore, Shop
from app.services.lotto_fetcher import fetch_latest_known, fetch_round, upsert_draw
from app.services.compare import score_recommendations_for_round
from app.services.shops_crawler import update_shops_round
from app.analysis import summary
from app.recommender import generate_full_and_semi
from app.cache import cache

api_bp = Blueprint("api", __name__)

@api_bp.get("/ping")
def ping():
    return jsonify({"status": "ok", "message": "pong"})

# --- Draws ---

@api_bp.get("/draws/latest")
def api_latest_draws():
    limit = int(request.args.get("limit", 10))
    rows = Draw.query.order_by(Draw.round.desc()).limit(limit).all()
    return jsonify([r.as_dict() for r in rows])

@api_bp.post("/draws/update-latest")
def api_update_latest():
    res = fetch_latest_known()
    if res is None:
        return jsonify({"updated": False, "message": "no new draw"}), 200
    score_recommendations_for_round(res.round)
    return jsonify({"updated": True, "last_round": res.round}), 200

@api_bp.post("/draws/update-range")
def api_update_range():
    body = request.get_json(silent=True) or {}
    start = int(body.get("start", 1))
    end = int(body.get("end", start))
    updated = 0
    for r in range(start, end + 1):
        d = fetch_round(r)
        if d:
            upsert_draw(d)
            updated += 1
    return jsonify({"updated_count": updated, "range": [start, end]})

# --- Analysis ---

@api_bp.get("/analysis/summary")
def api_analysis_summary():
    top_k = int(request.args.get("top", 10))
    return jsonify(summary(top_k=top_k))

# --- Recommendations ---

@api_bp.post("/recommendations/generate")
def api_generate_recommendations():
    body = request.get_json(silent=True) or {}
    round_arg = body.get("round")
    if round_arg is None:
        max_round = db.session.execute(db.text("SELECT MAX(round) FROM draws")).scalar()
        round_arg = (max_round or 0) + 1
    full5, semi5 = generate_full_and_semi(int(round_arg))
    return jsonify({"round": int(round_arg), "full": full5, "semi": semi5})

@api_bp.get("/recommendations/latest")
def api_list_recommendations():
    limit = int(request.args.get("limit", 10))
    rows = Recommendation.query.order_by(Recommendation.id.desc()).limit(limit).all()
    data = []
    for r in rows:
        data.append({
            "id": r.id, "round": r.round, "kind": r.kind,
            "numbers": r.numbers, "confidence": r.confidence, "reason": r.reason
        })
    return jsonify(data)

# --- Scoring ---

@api_bp.post("/recs/score")
def api_score_for_round():
    body = request.get_json(silent=True) or {}
    round_no = int(body.get("round", 0))
    if not round_no:
        return jsonify({"ok": False, "message": "round required"}), 400
    res = score_recommendations_for_round(round_no)
    return jsonify(res)

# --- Shops ---

@api_bp.post("/shops/update")
def api_shops_update():
    """
    /api/shops/update?round=1185
    """
    rnd = int(request.args.get("round", 0))
    if rnd <= 0:
        return jsonify({"ok": False, "message": "round param required"}), 400
    res = update_shops_round(rnd)
    return jsonify({"ok": True, **res})

@api_bp.get("/shops/query")
@cache.cached(timeout=600, query_string=True)  # 10분 캐시
def api_shops_query():
    rnd = request.args.get("round")
    q = Shop.query
    if rnd:
        q = q.filter(Shop.round == int(rnd))
    rows = q.order_by(Shop.round.desc(), Shop.id.asc()).limit(1000).all()
    data = []
    for s in rows:
        data.append({
            "id": s.id, "round": s.round, "rank": s.rank,
            "name": s.name, "address": s.address,
            "lat": s.lat, "lon": s.lon
        })
    return jsonify(data)
