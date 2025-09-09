# db.py — tiny sqlite helper
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv('DB_PATH', './data/storage.sqlite3')
Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

_conn = get_conn()

def init_db():
    cur = _conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    _conn.commit()

init_db()
