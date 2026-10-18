"""Behavioural baseline per agent and a lightweight, explainable anomaly score."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..models import AnomalyFactor, ToolCallEvent
from . import features as F

START = "<start>"


@dataclass
class Baseline:
    events: int = 0
    sessions: int = 0
    tool_counts: Counter = field(default_factory=Counter)
    resources: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    bigrams: Counter = field(default_factory=Counter)
    max_payload: dict[str, int] = field(default_factory=dict)
    max_per_session: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_events(cls, rows: list[dict]) -> "Baseline":
        b = cls()
        by_session: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_session[row["session_id"]].append(row)
        b.sessions = len(by_session)
        for session_rows in by_session.values():
            session_rows.sort(key=lambda r: (r.get("step") or 0, r["ts"]))
            prev = START
            per_session: Counter = Counter()
            for row in session_rows:
                tool, args = row["tool"], row["args"] or {}
                b.events += 1
                b.tool_counts[tool] += 1
                per_session[tool] += 1
                for key in F.resource_keys(tool, args):
                    b.resources[tool][key] += 1
                b.bigrams[(prev, tool)] += 1
                b.max_payload[tool] = max(b.max_payload.get(tool, 0), F.payload_size(args))
                prev = tool
            for tool, n in per_session.items():
                b.max_per_session[tool] = max(b.max_per_session.get(tool, 0), n)
        return b

    def summary(self) -> dict:
        return {
            "events": self.events,
            "sessions": self.sessions,
            "tools": dict(self.tool_counts),
            "resources": {t: dict(c) for t, c in self.resources.items()},
            "max_per_session": self.max_per_session,
        }


def score(event: ToolCallEvent, baseline: Baseline, session_count: int) -> tuple[float, list[AnomalyFactor]]:
    """Combine independent signals with noisy-OR: 1 - prod(1 - s_i)."""
    if baseline.events == 0:
        return 0.0, []
    factors: list[AnomalyFactor] = []
    tool = event.tool

    if baseline.tool_counts[tool] == 0:
        factors.append(AnomalyFactor(name="new_tool", score=0.95,
                                     detail=f"{tool} never used during {baseline.sessions} learned sessions"))
    else:
        seen = baseline.resources.get(tool, {})
        new = [k for k in F.resource_keys(tool, event.args) if seen.get(k, 0) == 0]
        if new:
            factors.append(AnomalyFactor(name="new_resource", score=0.55,
                                         detail=f"first time touching {', '.join(k.split(':', 1)[1] for k in new)} via {tool}"))

        prev = event.prev_tools[-1] if event.prev_tools else START
        if baseline.bigrams[(prev, tool)] == 0:
            factors.append(AnomalyFactor(name="unusual_sequence", score=0.3,
                                         detail=f"{prev} → {tool} never observed"))

        size, max_seen = F.payload_size(event.args), baseline.max_payload.get(tool, 0)
        if max_seen and size > max(3 * max_seen, 400):
            factors.append(AnomalyFactor(name="volume_spike", score=0.6,
                                         detail=f"payload {size} chars vs {max_seen} max seen"))

        max_calls = baseline.max_per_session.get(tool, 0)
        if session_count + 1 > 2 * max_calls + 1:
            factors.append(AnomalyFactor(name="burst", score=0.5,
                                         detail=f"{session_count + 1} {tool} calls this session vs {max_calls} max seen"))

    if event.tainted and factors:
        factors.append(AnomalyFactor(name="after_untrusted_input", score=0.25,
                                     detail=f"session read untrusted content ({', '.join(event.taint_sources[:2])})"))

    remaining = 1.0
    for f in factors:
        remaining *= 1 - f.score
    return round(1 - remaining, 3), factors
