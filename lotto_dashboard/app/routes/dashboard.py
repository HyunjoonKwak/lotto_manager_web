from flask import Blueprint, render_template, request, flash, redirect, url_for
from sqlalchemy import func
from ..extensions import db, cache
from ..models import Draw, Recommendation, Shop
from ..utils.scraper import iter_fetch_draws, fetch_shops
from ..utils.analysis import frequency_single, cold_numbers, frequency_pairs, last_seen_round
from ..utils.recommend import recommend_full_with_reasons, recommend_semi

bp = Blueprint("dashboard", __name__)

def _get_latest_round():
    r = db.session.query(func.max(Draw.round)).scalar()
    return r or 0

def _get_cached_recommendations(latest_round):
    """해당 회차의 캐시된 추천을 타입별 최신 5개씩 반환(없으면 None)."""
    # full 5개, semi 5개를 최신순으로 가져온 뒤 표시용으로 올바른 순서로 정렬
    full_q = (
        Recommendation.query
        .filter(Recommendation.round_expected == latest_round, Recommendation.type == "full")
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        .limit(5)
        .all()
    )
    semi_q = (
        Recommendation.query
        .filter(Recommendation.round_expected == latest_round, Recommendation.type == "semi")
        .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
        .limit(5)
        .all()
    )
    if not full_q or not semi_q:
        return None, None

    def parse_nums(s): return [int(x) for x in s.split(",") if x]
    # 최신순으로 뽑았으니 표시할 때는 역순으로(오래된→최신) 정렬하면 자연스러움
    full_wr = [(parse_nums(r.nums), r.note or "") for r in reversed(full_q)]
    semi_l  = [parse_nums(r.nums) for r in reversed(semi_q)]
    return full_wr, semi_l

def _generate_and_cache_recommendations(latest_round, draws_all):
    """새 추천 생성 후 DB에 저장하고 반환."""
    full_wr = recommend_full_with_reasons(draws_all, 5)
    semi_l = recommend_semi(draws_all, 5)
    for combo, reason in full_wr:
        db.session.add(Recommendation(
            type="full", nums=",".join(map(str, combo)),
            method="mix", note=reason, round_expected=latest_round
        ))
    for triple in semi_l:
        db.session.add(Recommendation(
            type="semi", nums=",".join(map(str, triple)),
            method="mix", note="semi-auto", round_expected=latest_round
        ))
    db.session.commit()
    return full_wr, semi_l

@bp.route("/", methods=["GET"])
def index():
    # 데이터 요약
    recent = Draw.query.order_by(Draw.round.desc()).limit(10).all()
    total_count = Draw.query.count()
    latest_round = _get_latest_round()
    latest_draw = Draw.query.filter_by(round=latest_round).first() if latest_round else None

    draws_all = Draw.query.order_by(Draw.round.asc()).all()
    singles = frequency_single(draws_all)[:15]
    pairs = frequency_pairs(draws_all, top_k=10)
    colds, latest = cold_numbers(draws_all, top_k=10)
    lastmap = last_seen_round(draws_all)

    # 추천: 캐시만 조회 (없어도 자동 생성 안 함)
    full_wr, semi = _get_cached_recommendations(latest_round)
    has_recommend = full_wr is not None and semi is not None
    if not has_recommend:
        full_wr, semi = [], []

    # 당첨점 조회(옵션)
    shops_round = request.args.get("round", type=int)
    shops = []
    if shops_round:
        shops = Shop.query.filter_by(round=shops_round).all()
        if not shops:
            rows = fetch_shops(shops_round)
            if rows:
                for r in rows:
                    db.session.add(Shop(
                        round=r["round"], rank=r.get("rank"),
                        name=r["name"], address=r.get("address"), method=r.get("method")
                    ))
                try:
                    db.session.commit()
                    shops = Shop.query.filter_by(round=shops_round).all()
                except Exception as e:
                    db.session.rollback()
                    flash(f"당첨점 저장 오류: {e}", "danger")
            if not shops:
                flash("해당 회차 당첨점 정보를 찾지 못했습니다.", "warning")

    return render_template(
        "dashboard.html",
        total_count=total_count,
        latest_round=latest_round,
        latest_draw=latest_draw,
        recent=recent,
        singles=singles, pairs=pairs,
        colds=colds, latest=latest, lastmap=lastmap,
        full_with_reason=full_wr, semi=semi,
        has_recommend=has_recommend,
        shops=shops, shops_round=shops_round
    )

@bp.route("/update", methods=["POST"])
def update_now():
    last = db.session.query(db.func.max(Draw.round)).scalar() or 0
    updated = 0
    for d in iter_fetch_draws(last+1):
        obj = Draw(
            round=d["round"], draw_date=d["draw_date"],
            n1=d["numbers"][0], n2=d["numbers"][1], n3=d["numbers"][2],
            n4=d["numbers"][3], n5=d["numbers"][4], n6=d["numbers"][5],
            bonus=d["bonus"]
        )
        db.session.add(obj); updated += 1
    if updated:
        db.session.commit()
        flash(f"업데이트 완료: {updated}건 추가", "success")
    else:
        flash("신규 회차가 없습니다.", "info")
    cache.clear()
    return redirect(url_for("dashboard.index"))

@bp.route("/recommend/refresh", methods=["POST"])
def refresh_recommend():
    """현재 최신 회차 캐시 전체 삭제 후 재생성(버튼으로만 갱신/생성)."""
    latest_round = _get_latest_round()
    if latest_round == 0:
        flash("데이터가 없어 추천을 생성할 수 없습니다.", "warning")
        return redirect(url_for("dashboard.index"))

    # 해당 회차 추천 전부 삭제(풀/세미) → 깔끔하게 한 세트만 유지
    Recommendation.query.filter(
        Recommendation.round_expected == latest_round
    ).delete(synchronize_session=False)
    db.session.commit()

    draws_all = Draw.query.order_by(Draw.round.asc()).all()
    _generate_and_cache_recommendations(latest_round, draws_all)
    cache.clear()
    flash("추천 번호를 새로 생성했습니다.", "success")
    return redirect(url_for("dashboard.index"))
