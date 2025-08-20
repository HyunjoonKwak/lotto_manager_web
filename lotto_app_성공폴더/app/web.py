from __future__ import annotations
import os
from flask import Flask, render_template, jsonify, abort, request
from dotenv import load_dotenv
load_dotenv()

from app.db import recent_rounds, get_draw, get_shops
from scripts.cli import fetch_and_store_round   # 재사용

# ★ app 폴더 하위의 templates/static 을 명시
APP_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(APP_DIR, "templates")
STATIC_DIR = os.path.join(APP_DIR, "static")

def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=TEMPLATE_DIR,
        static_folder=STATIC_DIR,
    )
    app.config["DATABASE"] = os.environ.get("DATABASE", "instance/lotto.db")
    os.makedirs(app.instance_path, exist_ok=True)

    @app.route("/")
    def home():
        rows = recent_rounds(limit=10)
        if not rows:
            from scripts.cli import cmd_fetch_latest
            try:
                cmd_fetch_latest(10)
                rows = recent_rounds(limit=10)
            except Exception:
                rows = []
        return render_template("home.html", draws=rows, title="로또 대시보드")

    @app.route("/round/<int:round_>")
    def round_page(round_: int):
        d = get_draw(round_)
        if not d:
            try:
                fetch_and_store_round(round_)
                d = get_draw(round_)
            except Exception:
                abort(404, f"{round_}회차 조회 실패")
        shops = get_shops(round_)
        return render_template("round.html", d=d, shops=shops, title=f"{round_}회차")

    # ---- JSON APIs ----
    @app.get("/api/draws")
    def api_draws():
        limit = int(request.args.get("limit", 10))
        rows = recent_rounds(limit=limit)
        payload = [dict(
            round=r["round"], date=r["draw_date"],
            numbers=[r["n1"],r["n2"],r["n3"],r["n4"],r["n5"],r["n6"]],
            bonus=r["bonus"]) for r in rows]
        return jsonify(payload)

    @app.get("/api/round/<int:round_>")
    def api_round(round_: int):
        d = get_draw(round_)
        if not d:
            try:
                fetch_and_store_round(round_)
                d = get_draw(round_)
            except Exception:
                abort(404)
        shops = get_shops(round_)
        return jsonify(dict(
            round=d["round"], date=d["draw_date"],
            numbers=[d["n1"],d["n2"],d["n3"],d["n4"],d["n5"],d["n6"]],
            bonus=d["bonus"],
            shops=[dict(name=s["name"], address=s["address"], type=s["type"]) for s in shops]
        ))

    return app

app = create_app()
