"""The decision engine: policy → task scope → taint → anomaly → verdict."""
from __future__ import annotations

import json
import logging
import statistics
import threading
import time
import uuid
from collections import Counter, defaultdict
from typing import Any, Callable

import httpx

from .. import config, llm
from ..models import Decision, ToolCallEvent
from . import anomaly, explain, learner
from . import features as F
from . import policy as P
from .audit import AuditLog
from .scope import TaskScoper
from .store import Store, now

log = logging.getLogger("agentleash.engine")

SEVERITY = {"ALLOW": 0, "NEEDS_APPROVAL": 1, "DENY": 2}

# Hook used by the evaluation harness to stand in for a human reviewer.
ApprovalOracle = Callable[[ToolCallEvent, Decision], bool]


class Engine:
    LAYERS = ("policy", "scope", "anomaly", "taint")

    def __init__(self, store: Store, use_llm: bool = True, notify: bool = True,
                 layers: tuple[str, ...] = LAYERS):
        self.store = store
        self.layers = set(layers)
        self.audit = AuditLog(store)
        self.use_llm = use_llm
        self.notify = notify
        self.scoper = TaskScoper(use_llm=use_llm)
        self.sessions: dict[str, P.SessionState] = defaultdict(P.SessionState)
        self.lock = threading.RLock()
        self._baselines: dict[str, anomaly.Baseline] = {}
        self._policies: dict[str, dict | None] = {}
        self.approval_oracle: ApprovalOracle | None = None

    # ------------------------------------------------------------------ agents
    def register_agent(self, agent_id: str, description: str = "", granted: list[str] | None = None,
                       mode: str = "learn") -> dict:
        existing = self.store.one("SELECT * FROM agents WHERE agent_id=?", (agent_id,))
        if existing:
            if granted and existing.get("granted") != granted:
                self.store.execute("UPDATE agents SET granted=?, description=? WHERE agent_id=?",
                                   (json.dumps(granted), description, agent_id))
            return self.store.one("SELECT * FROM agents WHERE agent_id=?", (agent_id,))
        row = {"agent_id": agent_id, "mode": mode, "description": description,
               "granted": granted or [], "created": now()}
        self.store.insert("agents", row)
        self.audit.append("agent_registered", {"agent_id": agent_id, "mode": mode})
        return row

    def agent(self, agent_id: str) -> dict:
        row = self.store.one("SELECT * FROM agents WHERE agent_id=?", (agent_id,))
        return row or self.register_agent(agent_id)

    def set_mode(self, agent_id: str, mode: str) -> None:
        if mode not in ("learn", "simulate", "enforce"):
            raise ValueError(f"unknown mode {mode}")
        self.agent(agent_id)
        self.store.execute("UPDATE agents SET mode=? WHERE agent_id=?", (mode, agent_id))
        self.audit.append("mode_changed", {"agent_id": agent_id, "mode": mode})

    # ---------------------------------------------------------------- policies
    def policy(self, agent_id: str) -> dict | None:
        if agent_id not in self._policies:
            row = self.store.one("SELECT yaml FROM policies WHERE agent_id=? ORDER BY version DESC LIMIT 1", (agent_id,))
            self._policies[agent_id] = P.load(row["yaml"]) if row else None
        return self._policies[agent_id]

    def policy_versions(self, agent_id: str) -> list[dict]:
        return self.store.query("SELECT * FROM policies WHERE agent_id=? ORDER BY version DESC", (agent_id,))

    def save_policy(self, agent_id: str, text: str, source: str = "manual") -> dict:
        P.load(text)  # validate before storing
        row = self.store.one("SELECT MAX(version) AS v FROM policies WHERE agent_id=?", (agent_id,))
        version = (row["v"] or 0) + 1
        self.store.insert("policies", {"agent_id": agent_id, "version": version, "yaml": text,
                                       "source": source, "created": now()})
        self._policies.pop(agent_id, None)
        self.audit.append("policy_saved", {"agent_id": agent_id, "version": version, "source": source})
        return {"agent_id": agent_id, "version": version}

    def learn_events(self, agent_id: str) -> list[dict]:
        return self.store.query("SELECT * FROM events WHERE agent_id=? AND mode='learn' ORDER BY ts", (agent_id,))

    def generate_policy(self, agent_id: str) -> dict:
        rows = self.learn_events(agent_id)
        if not rows:
            raise ValueError("no learn-mode activity recorded for this agent yet")
        generated = learner.generate(agent_id, rows)
        saved = self.save_policy(agent_id, P.dump(generated), source="learned")
        self._baselines.pop(agent_id, None)
        return {**saved, "policy": generated}

    def baseline(self, agent_id: str) -> anomaly.Baseline:
        if agent_id not in self._baselines:
            self._baselines[agent_id] = anomaly.Baseline.from_events(self.learn_events(agent_id))
        return self._baselines[agent_id]

    # ---------------------------------------------------------------- decision
    def _decide(self, event: ToolCallEvent, session: P.SessionState, policy: dict | None,
                baseline: anomaly.Baseline) -> Decision:
        reasons: list[str] = []
        details: list[str] = []
        verdict = "ALLOW"

        def flag(v: str, code: str, detail: str) -> None:
            nonlocal verdict
            if code not in reasons:
                reasons.append(code)
                details.append(detail)
            if SEVERITY[v] > SEVERITY[verdict]:
                verdict = v

        # 1. Static least-privilege policy
        if policy is not None and "policy" in self.layers:
            for v in P.evaluate(policy, event, session):
                flag("DENY", v.code, v.detail)

        # 2. Task scope: narrow the policy to what this request needs
        available = sorted(policy["tools"]) if policy else sorted(set(baseline.tool_counts) | {event.tool})
        if session.scope is None:
            if "scope" in self.layers:
                sc = self.scoper.scope(event.task, available)
                session.scope, session.scope_sql_write = sc.tools, sc.sql_write
            else:
                session.scope, session.scope_sql_write = available, True
        if event.tool not in session.scope:
            flag("DENY" if event.risk == "high" else "NEEDS_APPROVAL", "outside_task_scope",
                 f"'{event.task[:80]}' does not need {event.tool}")
        elif event.tool == "query_db" and not session.scope_sql_write and not F.sql_info(event.args.get("sql", "")).readonly:
            flag("NEEDS_APPROVAL", "outside_task_scope", "the task does not ask to modify database records")

        # 3. Behavioural anomaly against the learned baseline
        score, factors = (anomaly.score(event, baseline, session.counts.get(event.tool, 0))
                          if "anomaly" in self.layers or "taint" in self.layers else (0.0, []))

        # 4. Taint: untrusted content was read earlier in this session. In the default
        #    "novel" mode a high-risk call is held only if anything about it is new;
        #    "strict" holds every high-risk call in a tainted session.
        taint = (policy or {}).get("taint", {})
        if "taint" in self.layers and event.tainted and event.risk == "high" and taint.get("high_risk_requires_approval", True):
            if taint.get("mode", "novel") == "strict" or factors:
                flag("NEEDS_APPROVAL", "tainted_high_risk",
                     f"high-risk {event.tool} after reading {', '.join(event.taint_sources[:2]) or 'untrusted content'}")

        if "anomaly" in self.layers and score >= config.DENY_THRESHOLD:
            flag("DENY", "anomalous", f"anomaly score {score:.2f} ≥ {config.DENY_THRESHOLD}")
        elif "anomaly" in self.layers and score >= config.APPROVAL_THRESHOLD:
            flag("NEEDS_APPROVAL", "anomalous", f"anomaly score {score:.2f} ≥ {config.APPROVAL_THRESHOLD}")

        return Decision(event_id=event.event_id, verdict=verdict, reasons=reasons, reason_details=details,
                        anomaly_score=score, anomaly_factors=factors, scope=session.scope or [])

    def authorize(self, event: ToolCallEvent) -> Decision:
        t0 = time.perf_counter()
        agent = self.agent(event.agent_id)
        mode = agent["mode"]
        with self.lock:
            session = self.sessions[event.session_id]
            if mode == "learn":
                decision = Decision(event_id=event.event_id, verdict="ALLOW", reasons=["learning"], mode="learn")
            else:
                decision = self._decide(event, session, self.policy(event.agent_id), self.baseline(event.agent_id))
                decision.mode = mode
            decision.latency_ms = round((time.perf_counter() - t0) * 1000, 3)

            if decision.verdict != "ALLOW":
                decision.explanation = explain.explain(event, decision, use_llm=self.use_llm)
            if mode == "simulate":
                decision.simulated_verdict, decision.verdict = decision.verdict, "ALLOW"
            if decision.verdict == "NEEDS_APPROVAL":
                decision.approval_id = uuid.uuid4().hex[:10]
            if decision.verdict == "ALLOW":
                session.record(event.tool, event.args)

        self._persist(event, decision)
        if decision.approval_id:
            self._open_approval(event, decision)
        return decision

    def _persist(self, event: ToolCallEvent, d: Decision) -> None:
        self.store.insert("events", {
            "event_id": event.event_id, "ts": event.ts, "agent_id": event.agent_id,
            "session_id": event.session_id, "mode": d.mode, "task": event.task, "tool": event.tool,
            "args": event.args, "risk": event.risk, "tainted": int(event.tainted),
            "taint_sources": event.taint_sources, "step": event.step, "verdict": d.verdict,
            "simulated_verdict": d.simulated_verdict, "reasons": d.reasons, "reason_details": d.reason_details,
            "anomaly_score": d.anomaly_score, "anomaly_factors": [f.model_dump() for f in d.anomaly_factors],
            "scope": d.scope, "explanation": d.explanation, "approval_id": d.approval_id,
            "latency_ms": d.latency_ms,
        })
        if d.mode == "learn":
            self._baselines.pop(event.agent_id, None)
        self.audit.append("decision", {
            "event_id": event.event_id, "agent_id": event.agent_id, "tool": event.tool,
            "verdict": d.verdict, "simulated_verdict": d.simulated_verdict, "reasons": d.reasons,
        })

    # --------------------------------------------------------------- approvals
    def _open_approval(self, event: ToolCallEvent, d: Decision) -> None:
        self.store.insert("approvals", {"approval_id": d.approval_id, "event_id": event.event_id,
                                        "agent_id": event.agent_id, "status": "pending", "created": now()})
        if self.approval_oracle is not None:
            self.decide_approval(d.approval_id, self.approval_oracle(event, d), by="oracle")
        elif self.notify and config.SLACK_WEBHOOK_URL:
            threading.Thread(target=self._slack, args=(event, d), daemon=True).start()

    def _slack(self, event: ToolCallEvent, d: Decision) -> None:
        text = (f":rotating_light: *AgentLeash approval needed* — `{event.agent_id}` wants `{event.tool}`\n"
                f"{d.explanation}\nReview: {config.DASHBOARD_URL}/#/approvals")
        try:
            httpx.post(config.SLACK_WEBHOOK_URL, json={"text": text}, timeout=5)
        except httpx.HTTPError as exc:
            log.warning("slack notify failed: %s", exc)

    def decide_approval(self, approval_id: str, approve: bool, by: str = "dashboard") -> dict:
        row = self.store.one("SELECT * FROM approvals WHERE approval_id=?", (approval_id,))
        if not row:
            raise KeyError(approval_id)
        if row["status"] != "pending":
            return row
        status = "approved" if approve else "denied"
        self.store.execute("UPDATE approvals SET status=?, decided=?, decided_by=? WHERE approval_id=?",
                           (status, now(), by, approval_id))
        if approve:
            ev = self.store.one("SELECT session_id, tool, args FROM events WHERE event_id=?", (row["event_id"],))
            if ev:
                with self.lock:
                    self.sessions[ev["session_id"]].record(ev["tool"], ev["args"])
        self.audit.append("approval", {"approval_id": approval_id, "status": status, "by": by})
        return {**row, "status": status, "decided_by": by}

    def approval_status(self, approval_id: str) -> dict | None:
        return self.store.one("SELECT * FROM approvals WHERE approval_id=?", (approval_id,))

    def wait_for_approval(self, approval_id: str, timeout: float | None = None) -> str:
        deadline = time.time() + (config.APPROVAL_TIMEOUT_S if timeout is None else timeout)
        while True:
            row = self.approval_status(approval_id)
            if row and row["status"] != "pending":
                return row["status"]
            if time.time() >= deadline:
                self.store.execute("UPDATE approvals SET status='expired', decided=? WHERE approval_id=? AND status='pending'",
                                   (now(), approval_id))
                return "expired"
            time.sleep(0.25)

    def pending_approvals(self) -> list[dict]:
        return self.store.query(
            "SELECT a.*, e.tool, e.args, e.task, e.explanation, e.reasons, e.reason_details, e.anomaly_score, "
            "e.taint_sources, e.risk FROM approvals a JOIN events e ON e.event_id=a.event_id "
            "WHERE a.status='pending' ORDER BY a.created DESC")

    # ------------------------------------------------------------ simulation
    def replay(self, agent_id: str, policy_text: str | None = None, limit: int = 1000) -> dict:
        """Re-run recorded traffic against a (proposed) policy without enforcing anything."""
        pol = P.load(policy_text) if policy_text else self.policy(agent_id)
        rows = self.store.query("SELECT * FROM events WHERE agent_id=? ORDER BY ts DESC LIMIT ?", (agent_id, limit))
        rows.reverse()
        sessions: dict[str, P.SessionState] = defaultdict(P.SessionState)
        baseline = self.baseline(agent_id)
        tally: Counter = Counter()
        changed = []
        for r in rows:
            ev = ToolCallEvent(agent_id=agent_id, session_id=r["session_id"], task=r["task"] or "", tool=r["tool"],
                               args=r["args"] or {}, risk=r["risk"] or "low", tainted=bool(r["tainted"]),
                               taint_sources=r["taint_sources"] or [], step=r["step"] or 0,
                               prev_tools=[t for t, _ in sessions[r["session_id"]].calls][-5:], event_id=r["event_id"])
            d = self._decide(ev, sessions[r["session_id"]], pol, baseline)
            tally[d.verdict] += 1
            if d.verdict == "ALLOW":
                sessions[r["session_id"]].record(ev.tool, ev.args)
            original = r["simulated_verdict"] or r["verdict"]
            if d.verdict != original:
                changed.append({"event_id": r["event_id"], "tool": r["tool"], "task": r["task"],
                                "was": original, "now": d.verdict, "reasons": d.reasons})
        return {"events": len(rows), "verdicts": dict(tally), "changed": changed[-50:]}

    # ---------------------------------------------------------------- insight
    def permissions(self, agent_id: str) -> dict:
        granted = self.agent(agent_id).get("granted") or []
        rows = self.store.query("SELECT tool, args FROM events WHERE agent_id=? AND verdict='ALLOW'", (agent_id,))
        used: Counter = Counter()
        for r in rows:
            for key in F.permission_keys(r["tool"], r["args"] or {}):
                used[key] += 1
        used_granted = sorted(k for k in used if k in granted)
        return {"granted": granted, "used": used_granted, "usage": dict(used),
                "unused": sorted(set(granted) - set(used_granted))}

    def stats(self) -> dict[str, Any]:
        rows = self.store.query("SELECT ts, verdict, simulated_verdict, mode, latency_ms, agent_id FROM events")
        verdicts = Counter(r["verdict"] for r in rows)
        lat = sorted(r["latency_ms"] for r in rows if r["mode"] != "learn" and r["latency_ms"] is not None)
        pct = lambda q: round(lat[min(len(lat) - 1, int(q * len(lat)))], 2) if lat else None
        pending = self.store.one("SELECT COUNT(*) AS n FROM approvals WHERE status='pending'")["n"]
        agents = self.store.query("SELECT agent_id, mode FROM agents")
        granted = used = 0
        for a in agents:
            p = self.permissions(a["agent_id"])
            granted += len(p["granted"])
            used += len(p["used"])
        return {
            "events": len(rows),
            "verdicts": {k: verdicts.get(k, 0) for k in ("ALLOW", "DENY", "NEEDS_APPROVAL")},
            "simulated_blocks": sum(1 for r in rows if r["simulated_verdict"] in ("DENY", "NEEDS_APPROVAL")),
            "latency_p50_ms": pct(0.5), "latency_p95_ms": pct(0.95),
            "latency_mean_ms": round(statistics.fmean(lat), 2) if lat else None,
            "pending_approvals": pending,
            "agents": len(agents),
            "permissions_granted": granted, "permissions_used": used,
            "llm": self.use_llm and llm.available(),
        }

    def timeline(self, buckets: int = 24, window_s: int = 3600) -> dict:
        end = now()
        size = window_s / buckets
        start = end - window_s
        rows = self.store.query("SELECT ts, verdict FROM events WHERE ts>=? AND mode!='learn'", (start,))
        out = [{"t": start + i * size, "ALLOW": 0, "DENY": 0, "NEEDS_APPROVAL": 0} for i in range(buckets)]
        for r in rows:
            i = min(buckets - 1, int((r["ts"] - start) / size))
            out[i][r["verdict"]] += 1
        return {"bucket_s": size, "buckets": out}

    def reset_sessions(self) -> None:
        with self.lock:
            self.sessions.clear()
