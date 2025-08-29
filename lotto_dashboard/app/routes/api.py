# app/routes/api.py
from __future__ import annotations

from typing import Any, Dict
from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("api", __name__)

# -----------------------------------------------------------------------------
# (기존) 당첨점 강제 수집 API - 유지
# -----------------------------------------------------------------------------
@bp.route("/api/shops/fetch", methods=["POST"])
def api_fetch_shops():
    """
    body: { "round": 1185, "rank": 1 }
    """
    data: Dict[str, Any] = request.get_json(silent=True) or request.form.to_dict()
    try:
        round_no = int(data.get("round", 0))
        rank = int(data.get("rank", 1))
    except Exception:
        return jsonify({"ok": False, "error": "invalid round/rank"}), 400

    try:
        # scripts.fetch_shops_override.fetch_shops 사용
        from scripts.fetch_shops_override import fetch_shops  # type: ignore
        inserted = fetch_shops(round_no, rank)
        return jsonify({"ok": True, "round": round_no, "rank": rank, "inserted": inserted})
    except Exception as e:
        current_app.logger.exception("[api.shops.fetch] error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500

# -----------------------------------------------------------------------------
# (신규) 당첨번호 수집 API
# -----------------------------------------------------------------------------
@bp.route("/api/numbers/fetch", methods=["POST"])
def api_fetch_numbers():
    """
    JSON 또는 form로 호출:
      - 모드 선택:
        * {"mode":"single", "round":1185}
        * {"mode":"range", "start":1100, "end":1185}
        * {"mode":"latest"}             # DB의 최대회차 이후로 최신까지 최대 10회 추정 수집
        * {"mode":"recent", "n":5}      # 최근 N회 보장(대시보드 버튼과 동일)
    """
    payload: Dict[str, Any] = request.get_json(silent=True) or request.form.to_dict()
    mode = (payload.get("mode") or "single").strip().lower()

    try:
        from app.utils.scraper import (
            fetch_and_store_round, fetch_numbers_range,
            fetch_latest_until_fail, update_recent_data
        )
    except Exception as e:
        current_app.logger.exception("[api.numbers.fetch] import error: %s", e)
        return jsonify({"ok": False, "error": "scraper import failed"}), 500

    try:
        if mode == "single":
            round_no = int(payload.get("round"))
            ok = fetch_and_store_round(current_app, round_no)
            return jsonify({"ok": ok, "mode": mode, "round": round_no})

        elif mode == "range":
            start = int(payload.get("start"))
            end = int(payload.get("end"))
            saved = fetch_numbers_range(current_app, start, end)
            return jsonify({"ok": True, "mode": mode, "start": start, "end": end, "saved": saved})

        elif mode == "latest":
            start, saved = fetch_latest_until_fail(current_app, max_probe=20)
            return jsonify({"ok": True, "mode": mode, "start_probe": start, "saved": saved})

        elif mode == "recent":
            n = int(payload.get("n", 5))
            info = update_recent_data(current_app, recent=n)
            return jsonify({"ok": True, "mode": mode, **info})

        else:
            return jsonify({"ok": False, "error": f"unknown mode: {mode}"}), 400

    except Exception as e:
        current_app.logger.exception("[api.numbers.fetch] runtime error: %s", e)
        return jsonify({"ok": False, "error": str(e)}), 500
