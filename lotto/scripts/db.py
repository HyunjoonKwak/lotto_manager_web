import sqlite3
from contextlib import contextmanager
from config import DB_PATH

PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA temp_store=MEMORY;",
    "PRAGMA cache_size=-20000;"  # ~20MB
]

def init_connection(conn: sqlite3.Connection):
    for p in PRAGMAS:
        conn.execute(p)
    conn.row_factory = sqlite3.Row

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)  # autocommit
    try:
        init_connection(conn)
        yield conn
    finally:
        conn.close()
