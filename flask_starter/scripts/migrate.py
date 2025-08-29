from __future__ import annotations

import sys
from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "instance" / "lotto.db"


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols


def ensure_columns() -> None:
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}. Run scripts.init_db first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    try:
        # Add sequence INTEGER column
        if not column_exists(conn, "winning_shops", "sequence"):
            conn.execute("ALTER TABLE winning_shops ADD COLUMN sequence INTEGER")
            print("Added column: winning_shops.sequence")

        # Add method VARCHAR(20) column
        if not column_exists(conn, "winning_shops", "method"):
            conn.execute("ALTER TABLE winning_shops ADD COLUMN method VARCHAR(20)")
            print("Added column: winning_shops.method")

        conn.commit()
    finally:
        conn.close()


def main() -> None:
    ensure_columns()
    print("Migration complete.")


if __name__ == "__main__":
    main()
