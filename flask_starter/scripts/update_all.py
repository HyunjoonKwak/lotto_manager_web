from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import Draw
from app.services.updater import get_latest_round, update_range


def main() -> None:
    app = create_app()
    with app.app_context():
        latest = get_latest_round()
        if not latest:
            print("Could not detect latest round")
            return
        current = Draw.query.order_by(Draw.round.desc()).first()
        start = (current.round + 1) if current else 1
        if start > latest:
            print("Already up to date")
            return
        update_range(start, latest)
        print(f"Updated rounds {start}..{latest}")


if __name__ == "__main__":
    main()
