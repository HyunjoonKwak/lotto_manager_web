import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db


def main() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database tables created.")


if __name__ == "__main__":
    main()
