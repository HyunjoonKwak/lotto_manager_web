from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import Draw, WinningShop
from app.services.lotto_fetcher import fetch_draw, fetch_winning_shops


def update_range(app: Flask, start_round: int, end_round: int) -> None:
    with app.app_context():
        for r in range(start_round, end_round + 1):
            data = fetch_draw(r)
            numbers = ",".join(str(n) for n in data["numbers"])
            draw = Draw.query.filter_by(round=r).first()
            if not draw:
                draw = Draw(round=r)
                db.session.add(draw)
            draw.draw_date = data["draw_date"]
            draw.numbers = numbers
            draw.bonus = data["bonus"]
            db.session.commit()

            shops = fetch_winning_shops(r)
            if shops:
                WinningShop.query.filter_by(round=r).delete()
                for s in shops:
                    db.session.add(
                        WinningShop(
                            round=r,
                            rank=s["rank"],
                            name=s["name"],
                            address=s.get("address"),
                            winners_count=s.get("winners_count"),
                        )
                    )
                db.session.commit()
            print(f"Round {r} updated")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.update_rounds <start_round> <end_round>")
        sys.exit(1)
    start_round = int(sys.argv[1])
    end_round = int(sys.argv[2])
    app = create_app()
    update_range(app, start_round, end_round)


if __name__ == "__main__":
    main()
