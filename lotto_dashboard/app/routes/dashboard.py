# app/routes/dashboard.py
from __future__ import annotations

import os
import sqlite3
from typing import Dict, List, Tuple, Any
from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, render_template

bp = Blueprint("dashboard", __name__)

# ---- helpers ---------------------------------------------------------------

def _db_path(app) -> str:
    inst_dir = getattr(app, "instance_path", None) or os.path.join(os.getcwd(), "instance")
    os.makedirs(inst_dir, exist_ok=True)
    return os.path.join(inst_dir, "lotto.db")

def _fetch_numbers(db_path: str, limit: int = 120) -> List[sqlite3.Row]:
    if not os.path.exists(db_path):
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                "SELECT round, n1,n2,n3,n4,n5,n6,bn, draw_date "
                "FROM numbers ORDER BY round DESC LIMIT ?", (limit,)
            ).fetchall()
        except sqlite3.OperationalError:
            # numbers 테이블이 아직 없거나 초기화 전
            return []

def _compute_freq_and_last(rows: List[sqlite3.Row]) -> Tuple[Dict[int,int], Dict[int,int], int | None, List[int]]:
    """
    rows: 최신 회차부터 내림차순 정렬된 rows
    반환:
      - freqmap: 각 번호(1~45) 등장 횟수
      - lastmap: 각 번호(1~45)가 '마지막으로 등장한 이후 지난 회차 수' (최신 회차=0)
      - latest_round: 최신 회차 번호 또는 None
      - last_numbers: 최신 회차 번호들 [n1..n6] (없으면 [])
    """
    freqmap: Dict[int, int] = {i: 0 for i in range(1, 46)}
    lastmap: Dict[int, int] = {i: 0 for i in range(1, 46)}
    latest_round: int | None = None
    last_numbers: List[int] = []

    if not rows:
        return freqmap, lastmap, latest_round, last_numbers

    # 최신 회차
    latest = rows[0]
    latest_round = int(latest["round"])
    last_numbers = [int(latest[k]) for k in ("n1","n2","n3","n4","n5","n6")]

    # 빈도 집계
    for r in rows:
        for k in ("n1","n2","n3","n4","n5","n6"):
            v = int(r[k])
            if 1 <= v <= 45:
                freqmap[v] += 1

    # 마지막 등장 이후 경과 회차 수(가장 최근 rows[0] 기준 0)
    latest_index_for: Dict[int, int] = {}
    for idx, r in enumerate(rows):  # 0=최신
        for k in ("n1","n2","n3","n4","n5","n6"):
            v = int(r[k])
            if v not in latest_index_for:
                latest_index_for[v] = idx
    for n in range(1, 46):
        lastmap[n] = latest_index_for.get(n, len(rows))

    return freqmap, lastmap, latest_round, last_numbers

def _fetch_latest_shops(db_path: str, top_k: int = 10) -> Tuple[int | None, List[Dict[str, Any]]]:
    """
    최신 회차의 1등 당첨점 일부를 보여주기 위한 간단 조회.
    (shops 테이블이 없거나 비어있어도 안전)
    """
    if not os.path.exists(db_path):
        return None, []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT MAX(round) AS mr FROM shops").fetchone()
            if not row or row["mr"] is None:
                return None, []
            latest_round = int(row["mr"])
            shops = conn.execute(
                "SELECT round, rank, name, address, method "
                "FROM shops WHERE round = ? AND rank = 1 "
                "ORDER BY name LIMIT ?",
                (latest_round, top_k),
            ).fetchall()
            return latest_round, [dict(s) for s in shops]
        except sqlite3.OperationalError:
            return None, []

# ---- routes ----------------------------------------------------------------

@bp.route("/", methods=["GET"])
def index():
    # 쿼리스트링으로 최근 N회 분석 등 옵션(기본 120)
    try:
        limit = int(request.args.get("limit", "120"))
        if limit <= 0:
            limit = 120
    except ValueError:
        limit = 120

    db_path = _db_path(current_app)

    # numbers 안전 조회
    rows = _fetch_numbers(db_path, limit=limit)
    freqmap, lastmap, latest_round, last_numbers = _compute_freq_and_last(rows)

    # shops 최신 회차 일부 미리보기(없어도 빈 목록)
    shops_round, shops_latest = _fetch_latest_shops(db_path, top_k=10)

    # 템플릿이 필요로 하는 값들을 항상 채워서 전달
    return render_template(
        "dashboard.html",
        latest_round=latest_round,
        last_numbers=last_numbers,
        freqmap=freqmap,
        lastmap=lastmap,
        rows=rows,                 # 최근 회차 카드 등에서 활용 가능
        shops_latest_round=shops_round,
        shops_latest=shops_latest,
    )

@bp.route("/update", methods=["POST"])
def update_now():
    """
    '최근 N회 업데이트' 버튼 처리.
    내부 유틸이 없더라도 예외 삼켜서 항상 대시보드로 리다이렉트.
    """
    try:
        recent = int(request.form.get("recent", "5"))
        if recent <= 0:
            recent = 5
    except Exception:
        recent = 5

    try:
        # 프로젝트 유틸 존재 시 사용
        from app.utils.scraper import update_recent_data  # type: ignore
        update_recent_data(current_app, recent=recent)
    except Exception as e:
        current_app.logger.warning("[dashboard.update_now] fallback: %s", e)

    return redirect(url_for("dashboard.index"))

@bp.route("/recommend/refresh", methods=["POST"])
def refresh_recommend():
    """
    템플릿에서 사용하는 추천 갱신 버튼 훅.
    실제 구현은 app.utils.recommend 또는 recommend 블루프린트에 있을 수 있으므로
    여기서는 있으면 호출, 없으면 조용히 무시하고 대시보드로 복귀한다.
    """
    handled = False
    # 1) 유틸 함수가 있으면 호출
    try:
        from app.utils.recommend import refresh_recommendations  # type: ignore
        try:
            refresh_recommendations(current_app)
            handled = True
        except Exception as e:
            current_app.logger.warning("[dashboard.refresh_recommend] util call failed: %s", e)
    except Exception:
        pass

    # 2) 라우트가 별도 recommend 블루프린트에 있다면 내부 호출 대신 로그만 남기고 넘어간다.
    if not handled:
        current_app.logger.info("[dashboard.refresh_recommend] no-op (no util found)")

    return redirect(url_for("dashboard.index"))

@bp.route("/numbers/fetch", methods=["POST"])
def fetch_numbers_action():
    """
    대시보드에서 숫자 수집 버튼(단일/구간/최신/최근N회)을 눌렀을 때 처리.
    """
    mode = (request.form.get("mode") or "single").strip().lower()

    # utils.scraper 의 숫자 수집 유틸 사용
    from app.utils.scraper import (
        fetch_and_store_round, fetch_numbers_range,
        fetch_latest_until_fail, update_recent_data
    )

    try:
        if mode == "single":
            round_no = int(request.form.get("round") or 0)
            ok = fetch_and_store_round(current_app, round_no)
            flash(f"[당첨번호] 회차 {round_no} {'저장완료' if ok else '실패'}", "info")

        elif mode == "range":
            start = int(request.form.get("start") or 0)
            end = int(request.form.get("end") or 0)
            saved = fetch_numbers_range(current_app, start, end)
            flash(f"[당첨번호] {start}~{end} 범위 저장 {saved}건", "info")

        elif mode == "latest":
            start_probe, saved = fetch_latest_until_fail(current_app, max_probe=20)
            flash(f"[당첨번호] 최신 회차 탐색 시작={start_probe}, 저장={saved}건", "info")

        elif mode == "recent":
            n = int(request.form.get("n") or 5)
            info = update_recent_data(current_app, recent=n)
            flash(f"[당첨번호] 최근 {n}회 보장: 채움 {info.get('filled',0)}건", "info")

        else:
            flash(f"알 수 없는 모드: {mode}", "warning")

    except Exception as e:
        current_app.logger.exception("[dashboard.fetch_numbers_action] %s", e)
        flash(f"[당첨번호] 오류: {e}", "danger")

    return redirect(url_for("dashboard.index"))
