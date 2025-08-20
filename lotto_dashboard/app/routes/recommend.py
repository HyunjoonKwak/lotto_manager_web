from flask import Blueprint, render_template
from ..extensions import db
from ..models import Draw, Recommendation
from ..utils.recommend import recommend_full_with_reasons, recommend_semi

bp = Blueprint("recommend", __name__)

@bp.route("/")
def recommend_home():
    draws = Draw.query.order_by(Draw.round.asc()).all()
    full_with_reason = recommend_full_with_reasons(draws, 5)
    semi = recommend_semi(draws, 5)

    # DB 저장 (이유 메모로 저장)
    for combo, reason in full_with_reason:
        db.session.add(Recommendation(type="full", nums=",".join(map(str, combo)), method="mix", note=reason))
    for triple in semi:
        db.session.add(Recommendation(type="semi", nums=",".join(map(str, triple)), method="mix", note="semi-auto"))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    # 템플릿은 기존 필드(full, semi) 사용
    full = [combo for combo, _ in full_with_reason]
    return render_template("recommend.html", full=full, semi=semi)
