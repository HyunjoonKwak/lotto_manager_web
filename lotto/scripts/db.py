import sqlite3
import contextlib
from config import DB as DB_PATH   # 호환용 alias

def get_conn():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row             # ★ 중요: dict(row) 가능하도록
    return con

@contextlib.contextmanager
def get_connection():
    con = get_conn()
    try:
        yield con
    finally:
        con.close()

def fetchone(sql, params=()):
    with get_connection() as con:
        cur = con.execute(sql, params)
        return cur.fetchone()

def fetchall(sql, params=()):
    with get_connection() as con:
        cur = con.execute(sql, params)
        return cur.fetchall()
