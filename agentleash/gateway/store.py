"""SQLite persistence for events, policies, approvals and the audit chain."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    task TEXT,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,
    risk TEXT,
    tainted INTEGER,
    taint_sources TEXT,
    step INTEGER,
    verdict TEXT NOT NULL,
    simulated_verdict TEXT,
    reasons TEXT,
    reason_details TEXT,
    anomaly_score REAL,
    anomaly_factors TEXT,
    scope TEXT,
    explanation TEXT,
    approval_id TEXT,
    latency_ms REAL
);
CREATE INDEX IF NOT EXISTS events_agent ON events(agent_id, ts);
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    description TEXT,
    granted TEXT,
    created REAL
);
CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    yaml TEXT NOT NULL,
    source TEXT,
    created REAL
);
CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    agent_id TEXT,
    status TEXT NOT NULL,
    created REAL,
    decided REAL,
    decided_by TEXT
);
CREATE TABLE IF NOT EXISTS audit (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
"""

JSON_COLUMNS = {"args", "taint_sources", "reasons", "reason_details", "anomaly_factors", "scope", "granted"}


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def query(self, sql: str, params: tuple | list = ()) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [self._decode(dict(r)) for r in rows]

    def one(self, sql: str, params: tuple | list = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        for key in JSON_COLUMNS & row.keys():
            if isinstance(row[key], str):
                try:
                    row[key] = json.loads(row[key])
                except json.JSONDecodeError:
                    pass
        return row

    def insert(self, table: str, row: dict[str, Any]) -> None:
        encoded = {
            k: json.dumps(v) if k in JSON_COLUMNS and not isinstance(v, str) else v
            for k, v in row.items()
        }
        cols = ", ".join(encoded)
        marks = ", ".join("?" for _ in encoded)
        self.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})", list(encoded.values()))

    def reset(self) -> None:
        with self.lock:
            for table in ("events", "agents", "policies", "approvals", "audit"):
                self.conn.execute(f"DELETE FROM {table}")
            self.conn.execute("DELETE FROM sqlite_sequence")
            self.conn.commit()


def now() -> float:
    return time.time()
