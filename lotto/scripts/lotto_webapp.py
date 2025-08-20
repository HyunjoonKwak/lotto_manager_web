# -*- coding: utf-8 -*-
import os, json, subprocess, csv
from flask import Flask, jsonify, request, render_template, Response
from db import get_conn
from lotto_recommender import generate_for_week, validate_week, ensure_tables as ensure_reco
from lotto_winshops import fetch_winshops_by_draw, fetch_latest_winshops  # fetch_latest_winshops는 예비용

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # /volume1/code_work/lotto
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

def get_latest_draw():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(draw_no) FROM lotto_results")
        return int(cur.fetchone()[0] or 0)

@app.route("/")
def index():
    ensure_reco()
    latest = get_latest_draw()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id,numbers,algorithm,confidence_score,reason,week_no,created_at
            FROM recommended_numbers WHERE algorithm='auto6'
            ORDER BY created_at DESC, id DESC LIMIT 5
        """)
        recent_auto6 = [dict(r) for r in cur.fetchall()]
        cur.execute("""
            SELECT id,numbers,algorithm,confidence_score,reason,week_no,created_at
            FROM recommended_numbers WHERE algorithm='semi_auto_digit3'
            ORDER BY created_at DESC, id DESC LIMIT 5
        """)
        recent_semi = [dict(r) for r in cur.fetchall()]
    return render_template("index.html", latest_draw=latest,
                           recent_auto6=recent_auto6, recent_semi=recent_semi)

# --- Draw API ---
@app.route("/api/draw/<int:draw_no>")
def api_draw(draw_no: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT draw_no, draw_date, num1,num2,num3,num4,num5,num6,bonus_num
          FROM lotto_results WHERE draw_no=?
        """, (draw_no,))
        r = cur.fetchone()
        if not r:
            return jsonify(success=False, error="not_found"), 404
        numbers = [int(r["num1"]),int(r["num2"]),int(r["3"]),int(r["num4"]),int(r["num5"]),int(r["num6"])] if "3" in r.keys() else [int(r["num1"]),int(r["num2"]),int(r["num3"]),int(r["num4"]),int(r["num5"]),int(r["num6"])]
        return jsonify(success=True, source="db", draw_no=r["draw_no"],
                       draw_date=r["draw_date"], numbers=numbers, bonus=int(r["bonus_num"]))

@app.route("/api/draw/recent")
def api_draw_recent():
    try:
        limit = int(request.args.get("limit", 10))
    except Exception:
        limit = 10
    limit = max(1, min(50, limit))
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT draw_no, draw_date, num1,num2,num3,num4,num5,num6,bonus_num
          FROM lotto_results
          ORDER BY draw_no DESC
          LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        items = []
        for r in rows:
            numbers = [int(r["num1"]),int(r["num2"]),int(r["num3"]),int(r["num4"]),int(r["num5"]),int(r["num6"])]
            items.append({"draw_no": r["draw_no"], "draw_date": r["draw_date"], "numbers": numbers, "bonus": int(r["bonus_num"])})
    return jsonify(success=True, count=len(items), items=items)

# --- Winshops API ---
@app.route("/api/winshops/latest")
def api_winshops_latest():
    from lotto_winshops import fetch_latest_winshops
    try:
        latest, shops = fetch_latest_winshops()
        # (옵션) 인터넷 판매처 숨기기 원하면 아래 필터 주석 해제
        # shops = [s for s in shops if (s.get("shop") or "") != "인터넷 복권판매사이트"]
        return jsonify({"success": True, "draw_no": latest, "count": len(shops), "shops": shops})
    except Exception as e:
        return jsonify({"success": False, "draw_no": 0, "count": 0, "shops": [], "error": str(e)}), 500


@app.route("/api/winshops/<int:draw_no>")
def api_winshops_draw(draw_no: int):
    from lotto_winshops import fetch_winshops_by_draw
    try:
        shops = fetch_winshops_by_draw(draw_no)
        # (옵션) 인터넷 판매처 숨기기
        # shops = [s for s in shops if (s.get("shop") or "") != "인터넷 복권판매사이트"]
        return jsonify({"success": True, "draw_no": draw_no, "count": len(shops), "shops": shops})
    except Exception as e:
        return jsonify({"success": False, "draw_no": draw_no, "count": 0, "shops": [], "error": str(e)}), 500

@app.route("/api/recommendations/generate", methods=["POST"])
def api_reco_generate():
    ensure_reco()
    latest = get_latest_draw()
    try:
        if request.data:
            payload = request.get_json(silent=True) or {}
            week_no = int(payload.get("week_no") or latest+1)
        else:
            week_no = latest + 1
    except Exception:
        week_no = latest + 1
    out_lines = []
    for name,slot,nums,ins in generate_for_week(week_no, per_algo=5):
        tag = "CREATED" if ins else "CACHED"
        out_lines.append(f"[{tag}] week={week_no} {name}[#{slot}]: {nums}")
    return jsonify(success=True, error="", output="\n".join(out_lines)+"\n")

@app.route("/api/recommendations/<int:week_no>")
def api_reco_list(week_no: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT id,numbers,algorithm,confidence_score,reason,week_no,slot,created_at
          FROM recommended_numbers WHERE week_no=?
          ORDER BY algorithm, slot, id
        """, (week_no,))
        rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "id": r["id"], "numbers": r["numbers"], "algorithm": r["algorithm"],
                "slot": r["slot"], "confidence": r["confidence_score"],
                "reason": r["reason"], "week_no": r["week_no"], "created_at": r["created_at"]
            })
    return jsonify(success=True, count=len(items), week_no=week_no, items=items)

@app.route("/api/recommendations/validate/<int:draw_no>", methods=["POST"])
def api_reco_validate(draw_no: int):
    res = validate_week(draw_no)
    return jsonify(success=True, stderr="", output=res)

@app.route("/api/recommendations/results/<int:draw_no>")
def api_reco_results(draw_no: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT rr.rec_id, rr.draw_no, rr.matched_count, rr.bonus_matched, rr.rank,
                 rn.algorithm, rn.numbers, rn.created_at
          FROM recommendation_results rr
          JOIN recommended_numbers rn ON rn.id = rr.rec_id
          WHERE rr.draw_no=?
          ORDER BY rr.id DESC
        """, (draw_no,))
        rows = cur.fetchall()
        items = []
        for r in rows:
            items.append({
                "rec_id": r["rec_id"], "draw_no": r["draw_no"],
                "matched": r["matched_count"], "bonus": r["bonus_matched"], "rank": r["rank"],
                "algorithm": r["algorithm"], "numbers": r["numbers"], "generated_at": r["created_at"]
            })
    return jsonify(success=True, count=len(items), draw_no=draw_no, items=items)

@app.route("/api/recommendations/results/<int:draw_no>/csv")
def api_reco_results_csv(draw_no: int):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT rr.rec_id, rr.draw_no, rr.matched_count, rr.bonus_matched, rr.rank,
                 rn.algorithm, rn.numbers, rn.created_at
          FROM recommendation_results rr
          JOIN recommended_numbers rn ON rn.id = rr.rec_id
          WHERE rr.draw_no=?
          ORDER BY rr.id DESC
        """, (draw_no,))
        rows = cur.fetchall()
    def gen():
        header = ["rec_id","draw_no","algorithm","numbers","matched","bonus","rank","generated_at"]
        yield ",".join(header) + "\n"
        for r in rows:
            vals = [str(r["rec_id"]), str(r["draw_no"]), r["algorithm"] or "", r["numbers"] or "",
                    str(r["matched_count"]), str(r["bonus_matched"]), r["rank"] or "", r["created_at"] or ""]
            esc = ['"'+v.replace('"','""')+'"' for v in vals]
            yield ",".join(esc) + "\n"
    return Response(gen(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="reco_results_{draw_no}.csv"'})

@app.route("/api/recommendations/recent")
def api_reco_recent():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
          SELECT id,numbers,algorithm,confidence_score,reason,week_no,created_at
          FROM recommended_numbers WHERE algorithm='auto6'
          ORDER BY created_at DESC, id DESC LIMIT 5
        """)
        auto6 = [dict(r) for r in cur.fetchall()]
        cur.execute("""
          SELECT id,numbers,algorithm,confidence_score,reason,week_no,created_at
          FROM recommended_numbers WHERE algorithm='semi_auto_digit3'
          ORDER BY created_at DESC, id DESC LIMIT 5
        """)
        semi = [dict(r) for r in cur.fetchall()]
    return jsonify(success=True, auto6=auto6, semi_auto=semi)

if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT","8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
