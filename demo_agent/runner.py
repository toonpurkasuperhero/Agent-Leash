"""Run a scenario (or a free-text task) against a sandbox, with or without AgentLeash."""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Callable

import yaml

from agentleash import config
from agentleash.sdk import CallResult, GuardedSession

from . import claude_agent, scripted
from .sandbox import Sandbox
from .tools import build_tools


@lru_cache(maxsize=1)
def scenarios() -> dict[str, list[dict]]:
    benign = yaml.safe_load((config.SCENARIO_DIR / "benign.yaml").read_text())
    attacks = yaml.safe_load((config.SCENARIO_DIR / "attacks.yaml").read_text())
    for s in benign:
        s["kind"] = "benign"
        s.setdefault("name", s["task"])
    for s in attacks:
        s["kind"] = "attack"
    return {"benign": benign, "attacks": attacks}


def find(scenario_id: str) -> dict:
    for group in scenarios().values():
        for s in group:
            if s["id"] == scenario_id:
                return s
    raise KeyError(scenario_id)


def step_view(r: CallResult) -> dict:
    d = r.decision
    return {
        "tool": r.tool, "args": {k: str(v)[:400] for k, v in r.args.items()}, "ok": r.ok,
        "output": r.output[:1200], "approval": r.approval,
        "verdict": (d.simulated_verdict or d.verdict) if d else None,
        "enforced": d.verdict if d else None,
        "mode": d.mode if d else None,
        "reasons": d.reasons if d else [], "explanation": d.explanation if d else None,
        "anomaly": d.anomaly_score if d else None, "event_id": d.event_id if d else None,
        "approval_id": d.approval_id if d else None,
    }


def run(scenario: dict, sb: Sandbox, client, agent_mode: str = "scripted",
        on_step: Callable[[CallResult], None] | None = None, approval_timeout: float = 120.0) -> dict:
    t0 = time.time()
    session = GuardedSession(client, scenario["agent"], scenario["task"], build_tools(sb),
                             approval_timeout=approval_timeout, on_step=on_step)
    if agent_mode == "claude":
        final = claude_agent.run(scenario["task"], session, scenario["agent"])
        user_steps = session.history
    else:
        final, user_steps = scripted.run(scenario, session, sb)
    return {
        "scenario": scenario.get("id"), "agent": scenario["agent"], "task": scenario["task"],
        "protected": client is not None, "session_id": session.session_id,
        "steps": [step_view(h) for h in session.history],
        "completed": all(h.ok for h in user_steps) if user_steps else False,
        "blocked": sum(1 for h in session.history if not h.ok),
        "needed_approval": any(h.approval for h in session.history),
        "damage": sb.damage(), "final": final, "seconds": round(time.time() - t0, 2),
    }
