from flask import Blueprint, jsonify
from ..extensions import db
from ..models import Draw
from ..utils.scraper import iter_fetch_draws
from ..utils.recommend import recommend_full_with_reasons, recommend_semi

bp = Blueprint("api", __name__)

@bp.post("/update")
def api_update():
    last = db.session.query(db.func.max(Draw.round)).scalar() or 0
    updated = 0
    for d in iter_fetch_draws(last+1):
        obj = Draw(round=d["round"], draw_date=d["draw_date"],
                   n1=d["numbers"][0], n2=d["numbers"][1], n3=d["numbers"][2],
                   n4=d["numbers"][3], n5=d["numbers"][4], n6=d["numbers"][5],
                   bonus=d["bonus"])
        db.session.add(obj)
        updated += 1
    if updated:
        db.session.commit()
    return jsonify({"updated": updated})

@bp.get("/recommend")
def api_recommend():
    draws = Draw.query.order_by(Draw.round.asc()).all()
    full_with_reason = recommend_full_with_reasons(draws, 5)
    full_only = [combo for combo, _ in full_with_reason]
    semi = recommend_semi(draws, 5)
    return jsonify({
        "full": full_only,
        "full_with_reason": [{"combo": combo, "reason": reason} for combo, reason in full_with_reason],
        "semi": semi,
    })
