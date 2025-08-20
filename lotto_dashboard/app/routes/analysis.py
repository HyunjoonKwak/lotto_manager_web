from flask import Blueprint, render_template
from ..extensions import cache
from ..models import Draw
from ..utils.analysis import frequency_single, frequency_pairs

bp = Blueprint("analysis", __name__)

@bp.route("/")
@cache.cached(timeout=6*3600)
def analysis_home():
    draws = Draw.query.order_by(Draw.round.asc()).all()
    singles = frequency_single(draws)
    pairs = frequency_pairs(draws, top_k=100)
    return render_template("analysis.html", singles=singles, pairs=pairs, total=len(draws))
