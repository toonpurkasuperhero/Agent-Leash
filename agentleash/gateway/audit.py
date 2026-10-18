"""Tamper-evident audit log: each row hashes its payload together with the previous row's hash."""
from __future__ import annotations

import hashlib
import json

from .store import Store, now

GENESIS = "0" * 64


def _digest(prev_hash: str, ts: float, kind: str, payload: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{ts:.6f}|{kind}|{payload}".encode()).hexdigest()


class AuditLog:
    def __init__(self, store: Store):
        self.store = store

    def append(self, kind: str, payload: dict) -> str:
        body = json.dumps(payload, sort_keys=True, default=str)
        with self.store.lock:
            last = self.store.one("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1")
            prev = last["hash"] if last else GENESIS
            ts = now()
            digest = _digest(prev, ts, kind, body)
            self.store.execute(
                "INSERT INTO audit (ts, kind, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?)",
                (ts, kind, body, prev, digest),
            )
        return digest

    def verify(self) -> dict:
        rows = self.store.query("SELECT * FROM audit ORDER BY seq")
        prev = GENESIS
        for row in rows:
            expected = _digest(prev, row["ts"], row["kind"], row["payload"])
            if row["prev_hash"] != prev or row["hash"] != expected:
                return {"ok": False, "rows": len(rows), "broken_at": row["seq"],
                        "detail": f"row {row['seq']} does not match its hash — the log was modified"}
            prev = row["hash"]
        return {"ok": True, "rows": len(rows), "head": prev}

    def tail(self, limit: int = 100) -> list[dict]:
        rows = self.store.query("SELECT * FROM audit ORDER BY seq DESC LIMIT ?", (limit,))
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return rows

    def tamper(self) -> dict | None:
        """Demo helper: silently rewrite one decision in the log, like an attacker covering tracks."""
        row = self.store.one(
            "SELECT * FROM audit WHERE kind='decision' AND payload LIKE '%\"DENY\"%' ORDER BY seq DESC LIMIT 1"
        ) or self.store.one("SELECT * FROM audit ORDER BY seq DESC LIMIT 1")
        if not row:
            return None
        payload = json.loads(row["payload"])
        payload["verdict"] = "ALLOW"
        payload["tampered"] = True
        self.store.execute("UPDATE audit SET payload=? WHERE seq=?",
                           (json.dumps(payload, sort_keys=True), row["seq"]))
        return {"seq": row["seq"]}
