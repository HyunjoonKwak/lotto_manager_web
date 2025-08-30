import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.services.updater import perform_update


def main() -> None:
    app = create_app()
    with app.app_context():
        if len(sys.argv) < 2:
            print("Usage: python update_rounds.py <round_number>")
            sys.exit(1)

        try:
            round_no = int(sys.argv[1])
            result = perform_update(round_no)
            print(f"Round {round_no}: {result}")
        except ValueError:
            print("Invalid round number")
            sys.exit(1)


if __name__ == "__main__":
    main()
