from __future__ import annotations

from typing import List, Iterable
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.utils.shops import fetch_rows as util_fetch_rows
from app.utils.shops import ensure_shops as util_ensure_shops

bp = Blueprint("shops", __name__, template_folder="../templates")


def _normalize_ranks(args) -> List[int]:
    ranks: List[int] = []
    for v in args.getlist("ranks"):
        try:
            iv = int(v)
            if iv in (1, 2):
                ranks.append(iv)
        except Exception:
            pass
    if not ranks and args.get("rank"):
        try:
            iv = int(args.get("rank"))
            if iv in (1, 2):
                ranks = [iv]
        except Exception:
            pass
    if not ranks:
        ranks = [1]
    return ranks


@bp.route("/", methods=["GET", "POST"])
def shops_home():
    if request.method == "POST":
        round_no = request.form.get("round", type=int)
        ranks = _normalize_ranks(request.form)
        q = request.form.get("q", "", type=str) or ""

        if not round_no:
            flash("회차를 입력해 주세요.", "warning")
            return redirect(url_for("shops.shops_home"))

        inserted = util_ensure_shops(current_app, round_no, ranks, force=True)
        if inserted > 0:
            flash(f"{round_no}회 {ranks}등 수집 저장: {inserted}건", "info")
        else:
            flash(f"{round_no}회 {ranks}등 수집할 데이터가 없거나 실패", "warning")

        return redirect(url_for("shops.shops_home", round=round_no, rank=ranks[0], q=q))

    # GET
    round_no = request.args.get("round", type=int)
    ranks = _normalize_ranks(request.args)
    q = request.args.get("q", "", type=str) or ""
    force = request.args.get("force", default=0, type=int)

    shops = []
    count = 0
    if round_no:
        try:
            shops = list(util_fetch_rows(current_app, round_no, ranks, q))
            count = len(shops)
        except Exception as e:
            flash(f"조회 중 오류: {e}", "danger")
            shops = []
            count = 0

        if count == 0 and force == 1:
            inserted = util_ensure_shops(current_app, round_no, ranks, force=True)
            if inserted > 0:
                flash(f"{round_no}회 {ranks}등 수집 저장: {inserted}건", "info")
            else:
                flash(f"{round_no}회 {ranks}등 수집할 데이터가 없거나 실패", "warning")
            return redirect(url_for("shops.shops_home", round=round_no, rank=ranks[0], q=q))

    return render_template(
        "shops.html",
        round_no=round_no,
        rank=ranks[0] if ranks else 1,
        ranks=ranks,
        q=q,
        shops=shops,
        count=count,
    )
