"""SQLite storage (plain sqlite3 - see AGENTS.md stack)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, created_at TEXT NOT NULL, lang TEXT DEFAULT 'en',
  partner_id TEXT, source TEXT DEFAULT 'direct'
);
CREATE TABLE IF NOT EXISTS business_profiles (
  session_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consents (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, purpose TEXT NOT NULL,
  text_version TEXT NOT NULL, granted_at TEXT NOT NULL, withdrawn_at TEXT
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, doc_type TEXT NOT NULL,
  filename TEXT, stored_path TEXT, uploaded_at TEXT NOT NULL,
  delete_after TEXT, deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS kyc_extractions (
  document_id TEXT PRIMARY KEY, fields_json TEXT NOT NULL, confidence_json TEXT NOT NULL,
  quality_json TEXT
);
CREATE TABLE IF NOT EXISTS kyc_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, check_code TEXT NOT NULL,
  status TEXT NOT NULL, detail TEXT, evidence_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quotes (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, rung TEXT, term_months INTEGER NOT NULL,
  total_monthly_inr INTEGER NOT NULL, total_setup_inr INTEGER NOT NULL, created_at TEXT NOT NULL,
  trace_json TEXT, items_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, quote_id TEXT NOT NULL, status TEXT NOT NULL,
  partner_id TEXT, created_at TEXT NOT NULL, expected_activation_date TEXT,
  data_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL, stage TEXT NOT NULL,
  status TEXT NOT NULL, at TEXT NOT NULL, note TEXT, pending_action TEXT
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL, channel TEXT NOT NULL,
  body TEXT NOT NULL, sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS partner_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id TEXT NOT NULL, token TEXT UNIQUE NOT NULL,
  lead_ref TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, session_id TEXT, detail_masked TEXT
);
CREATE TABLE IF NOT EXISTS handoffs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, reason TEXT NOT NULL,
  context_json TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS demo_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

_conn: sqlite3.Connection | None = None


def connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


@contextmanager
def cursor():
    conn = connect()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    finally:
        cur.close()


def now() -> str:
    """Audit timestamps only - never business date logic."""
    return datetime.now().isoformat(timespec="seconds")


def execute(sql: str, params: tuple = ()) -> None:
    with cursor() as cur:
        cur.execute(sql, params)


def insert(sql: str, params: tuple = ()) -> int:
    with cursor() as cur:
        cur.execute(sql, params)
        return int(cur.lastrowid or 0)


def query(sql: str, params: tuple = ()) -> list[dict]:
    with cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def one(sql: str, params: tuple = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def set_state(key: str, value: Any) -> None:
    execute(
        "INSERT INTO demo_state(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value)),
    )


def get_state(key: str, default: Any = None) -> Any:
    row = one("SELECT value FROM demo_state WHERE key = ?", (key,))
    return json.loads(row["value"]) if row else default
