import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.services.updater import update_to_latest


def main() -> None:
    app = create_app()
    with app.app_context():
        result = update_to_latest()
        print(f"Update result: {result}")


if __name__ == "__main__":
    main()
