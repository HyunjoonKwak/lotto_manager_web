from flask import Blueprint, render_template, request, flash
from sqlalchemy import or_, func
from ..extensions import db
from ..models import Shop, Draw
from ..utils.shops import fetch_shops_all_pages

bp = Blueprint("shops", __name__)

def _latest_round():
    r = db.session.query(func.max(Draw.round)).scalar()
    return r or 0

@bp.route("/", methods=["GET", "POST"])
def shops_home():
    round_no = request.values.get("round", type=int)
    rank = request.values.get("rank", type=int) or 1
    if not round_no:
        round_no = _latest_round()

    q = (request.values.get("q") or "").strip()
    fetched = False

    if not round_no:
        flash("회차 데이터가 아직 없습니다. 먼저 회차 데이터를 업데이트해 주세요.", "warning")
        return render_template("shops.html", shops=[], round_no=None, q=q, count=0, rank=rank)

    if request.method == "POST":
        rows = fetch_shops_all_pages(round_no, rank=rank)
        if rows:
            Shop.query.filter_by(round=round_no).delete(synchronize_session=False)
            for r in rows:
                db.session.add(Shop(round=r["round"], rank=r.get("rank"),
                                    name=r["name"], address=r.get("address"), method=r.get("method")))
            db.session.commit()
            fetched = True
        else:
            flash("크롤링 결과가 비었습니다. 잠시 후 다시 시도해 주세요. (logs/shops/*.debug.html 확인)", "warning")

    query = Shop.query.filter_by(round=round_no)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Shop.name.ilike(like), Shop.address.ilike(like)))
    shops = query.order_by(Shop.rank.asc(), Shop.id.asc()).all()

    if not shops and not fetched:
        rows = fetch_shops_all_pages(round_no, rank=rank)
        if rows:
            Shop.query.filter_by(round=round_no).delete(synchronize_session=False)
            for r in rows:
                db.session.add(Shop(round=r["round"], rank=r.get("rank"),
                                    name=r["name"], address=r.get("address"), method=r.get("method")))
            db.session.commit()
            shops = Shop.query.filter_by(round=round_no).order_by(Shop.rank.asc(), Shop.id.asc()).all()

    count = len(shops)
    return render_template("shops.html", shops=shops, round_no=round_no, q=q, count=count, rank=rank)
