# app/routes/info.py
from __future__ import annotations

import os
import sqlite3
from flask import Blueprint, current_app, render_template

bp = Blueprint("info", __name__, url_prefix="/info")

def _db_path(app) -> str:
    inst_dir = getattr(app, "instance_path", None) or os.path.join(os.getcwd(), "instance")
    os.makedirs(inst_dir, exist_ok=True)
    return os.path.join(inst_dir, "lotto.db")

def _fetch_numbers(db_path: str, limit: int = 120):
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
            return []

def _fetch_latest_shops(db_path: str, top_k: int = 10):
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

@bp.route("/")
def info_home():
    db_path = _db_path(current_app)
    rows = _fetch_numbers(db_path, limit=120)
    shops_round, shops_latest = _fetch_latest_shops(db_path, top_k=10)

    latest_round = None
    if rows:
        latest_round = int(rows[0]["round"])

    return render_template(
        "info.html",
        rows=rows,
        latest_round=latest_round,
        shops_latest_round=shops_round,
        shops_latest=shops_latest,
    )
