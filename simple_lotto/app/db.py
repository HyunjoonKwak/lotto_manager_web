from __future__ import annotations
import sqlite3, os, time
from typing import Iterable, Optional, Any, Dict

DB_PATH = os.environ.get("DATABASE", "instance/lotto.db")

def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS draws (
  round INTEGER PRIMARY KEY,
  draw_date TEXT NOT NULL,
  n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
  n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
  bonus INTEGER NOT NULL,
  raw_json TEXT NOT NULL,
  fetched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS shops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  round INTEGER NOT NULL,
  name TEXT NOT NULL,
  address TEXT NOT NULL DEFAULT '',
  type TEXT,
  lat REAL, lon REAL,
  source_url TEXT,
  fetched_at INTEGER NOT NULL,
  UNIQUE (round, name, address),
  FOREIGN KEY(round) REFERENCES draws(round)
);

CREATE TABLE IF NOT EXISTS meta_cache (
  cache_key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  fetched_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_shops_round ON shops(round);
"""

def init_db():
    with get_conn() as c:
        c.executescript(SCHEMA)

def upsert_draw(round_: int, draw_date: str, numbers: list[int], bonus: int, raw_json: str):
    with get_conn() as c:
        c.execute("""
        INSERT INTO draws (round, draw_date, n1,n2,n3,n4,n5,n6, bonus, raw_json, fetched_at)
        VALUES (?, ?, ?,?,?,?,?,?, ?, ?, ?)
        ON CONFLICT(round) DO UPDATE SET
          draw_date=excluded.draw_date,
          n1=excluded.n1,n2=excluded.n2,n3=excluded.n3,
          n4=excluded.n4,n5=excluded.n5,n6=excluded.n6,
          bonus=excluded.bonus, raw_json=excluded.raw_json,
          fetched_at=excluded.fetched_at
        """, (round_, draw_date, *numbers, bonus, raw_json, int(time.time())))

def insert_shops(round_: int, rows: Iterable[Dict[str, Any]]):
    rows = list(rows)
    if not rows: return
    ts = int(time.time())
    with get_conn() as c:
        c.executemany("""
        INSERT OR IGNORE INTO shops (round, name, address, type, lat, lon, source_url, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [(round_,
               (r.get("name","") or "").strip(),
               (r.get("address") or "").strip(),
               (r.get("type") or None),
               r.get("lat"), r.get("lon"),
               r.get("source_url"), ts) for r in rows])

def get_latest_round() -> Optional[int]:
    with get_conn() as c:
        row = c.execute("SELECT MAX(round) AS r FROM draws").fetchone()
    return row["r"] if row and row["r"] is not None else None

def get_draw(round_: int) -> Optional[sqlite3.Row]:
    with get_conn() as c:
        return c.execute("SELECT * FROM draws WHERE round=?", (round_,)).fetchone()

def get_shops(round_: int) -> list[sqlite3.Row]:
    with get_conn() as c:
        return c.execute("SELECT * FROM shops WHERE round=? ORDER BY name", (round_,)).fetchall()

def recent_rounds(limit: int = 10) -> list[sqlite3.Row]:
    with get_conn() as c:
        return c.execute("""
        SELECT * FROM draws ORDER BY round DESC LIMIT ?
        """, (limit,)).fetchall()

def stale_before(ttl_days: int) -> int:
    return int(time.time() - ttl_days * 86400)

def delete_shops(round_: int):
    with get_conn() as c:
        c.execute("DELETE FROM shops WHERE round=?", (round_,))
