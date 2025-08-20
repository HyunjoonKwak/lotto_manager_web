from flask import Blueprint, render_template, abort
from sqlalchemy import text
from app.models import Draw, Shop, Recommendation, db

web_bp = Blueprint("web", __name__)

@web_bp.route("/")
def index():
    # 홈은 대시보드로 리다이렉트 느낌으로 구성
    return render_template("dashboard.html", **_gather_dashboard())

@web_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", **_gather_dashboard())

def _gather_dashboard():
    # 최근 10회 추첨
    draws = Draw.query.order_by(Draw.round.desc()).limit(10).all()
    # 최신 회차 (숫자)
    last_round = db.session.execute(text("SELECT MAX(round) FROM draws")).scalar()
    # 최신 회차의 당첨점
    shops = []
    if last_round:
        shops = Shop.query.filter(Shop.round == last_round).order_by(Shop.rank.asc(), Shop.id.asc()).all()
    # 최근 추천 10건
    recs = Recommendation.query.order_by(Recommendation.id.desc()).limit(10).all()
    return {"draws": draws, "last_round": last_round, "shops": shops, "recs": recs}

@web_bp.route("/latest")
def latest():
    rows = Draw.query.order_by(Draw.round.desc()).limit(10).all()
    return render_template("draws.html", draws=rows)

@web_bp.route("/shops")
def shops_latest():
    last = db.session.execute(text("SELECT MAX(round) FROM draws")).scalar()
    if not last:
        abort(404)
    shops = Shop.query.filter(Shop.round == last).order_by(Shop.rank.asc(), Shop.id.asc()).all()
    return render_template("shops.html", round_no=last, shops=shops)

@web_bp.route("/shops/<int:round_no>")
def shops_by_round(round_no: int):
    shops = Shop.query.filter(Shop.round == round_no).order_by(Shop.rank.asc(), Shop.id.asc()).all()
    return render_template("shops.html", round_no=round_no, shops=shops)

@web_bp.route("/recs")
def rec_list_page():
    rows = Recommendation.query.order_by(Recommendation.id.desc()).limit(50).all()
    return render_template("recs.html", recs=rows)

@web_bp.route("/health")
def health():
    return "OK", 200
