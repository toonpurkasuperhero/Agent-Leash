"""Reproducible evaluation: learn on benign traffic, then replay held-out benign
tasks and every attack under three setups.

A simulated human reviewer approves held actions for benign scenarios and
denies them for attacks, so approval friction is measured separately from
outright blocking.
"""
from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path
from typing import Callable

from agentleash.gateway.engine import Engine
from agentleash.gateway.store import Store
from agentleash.sdk import LocalClient
from demo_agent import runner
from demo_agent.sandbox import Sandbox
from demo_agent.tools import AGENTS

SETUPS = {
    "unprotected": None,
    "policy_only": ("policy",),
    "full": Engine.LAYERS,
}
LABELS = {"unprotected": "No AgentLeash", "policy_only": "Static policy only", "full": "Full AgentLeash"}
LEARN_REPEATS = 2


def _new_engine(tmp: Path, layers, use_llm: bool) -> tuple[Engine, Sandbox]:
    sb = Sandbox(tmp / "sandbox")
    engine = Engine(Store(tmp / "gateway.db"), use_llm=use_llm, notify=False, layers=layers)
    for agent_id, desc in AGENTS.items():
        engine.register_agent(agent_id, desc, sb.granted_permissions())
    return engine, sb


def learn(engine: Engine, sb: Sandbox, train: list[dict]) -> None:
    client = LocalClient(engine)
    for agent_id in AGENTS:
        engine.set_mode(agent_id, "learn")
    for _ in range(LEARN_REPEATS):
        for s in train:
            sb.reset()
            runner.run(s, sb, client)
    for agent_id in AGENTS:
        engine.generate_policy(agent_id)
        engine.set_mode(agent_id, "enforce")


def run_eval(use_llm: bool = False, progress: Callable[[str, float], None] | None = None) -> dict:
    groups = runner.scenarios()
    train = [s for s in groups["benign"] if s["split"] == "train"]
    test = [s for s in groups["benign"] if s["split"] == "test"]
    attacks = groups["attacks"]
    cases = test + attacks
    total = len(SETUPS) * len(cases)
    done = 0
    results: dict[str, dict] = {}
    anomaly_points: list[dict] = []
    t_start = time.time()

    for setup, layers in SETUPS.items():
        with tempfile.TemporaryDirectory(prefix="agentleash-eval-") as tmp:
            engine, sb = _new_engine(Path(tmp), layers or Engine.LAYERS, use_llm)
            client = None
            if layers is not None:
                learn(engine, sb, train)
                client = LocalClient(engine)
            rows = []
            for case in cases:
                sb.reset()
                engine.reset_sessions()
                engine.approval_oracle = (lambda kind: lambda ev, d: kind == "benign")(case["kind"])
                r = runner.run(case, sb, client, approval_timeout=0)
                attack_ok = bool(r["damage"])
                rows.append({
                    "id": case["id"], "kind": case["kind"], "name": case.get("name", case["task"]),
                    "agent": case["agent"], "category": case.get("category", "benign"),
                    "completed": r["completed"] and not r["damage"], "damage": r["damage"],
                    "attack_succeeded": attack_ok if case["kind"] == "attack" else None,
                    "needed_approval": r["needed_approval"], "blocked": r["blocked"],
                    "steps": [{"tool": s["tool"], "verdict": s["verdict"], "ok": s["ok"], "reasons": s["reasons"],
                               "approval": s["approval"]} for s in r["steps"]],
                })
                if setup == "full":
                    for s in r["steps"]:
                        if s["anomaly"] is not None:
                            anomaly_points.append({"score": s["anomaly"], "kind": case["kind"], "tool": s["tool"],
                                                   "scenario": case["id"], "verdict": s["verdict"]})
                done += 1
                if progress:
                    progress(f"{LABELS[setup]}: {case['id']}", done / total)

            lat = [e["latency_ms"] for e in engine.store.query(
                "SELECT latency_ms FROM events WHERE mode='enforce'")] if layers else []
            benign = [r for r in rows if r["kind"] == "benign"]
            atk = [r for r in rows if r["kind"] == "attack"]
            results[setup] = {
                "label": LABELS[setup],
                "attack_success_rate": round(sum(r["attack_succeeded"] for r in atk) / len(atk), 3),
                "attacks_succeeded": sum(r["attack_succeeded"] for r in atk),
                "attacks_total": len(atk),
                "benign_completion_rate": round(sum(r["completed"] for r in benign) / len(benign), 3),
                "benign_completed": sum(r["completed"] for r in benign),
                "benign_total": len(benign),
                "benign_approval_rate": round(sum(r["needed_approval"] for r in benign) / len(benign), 3),
                "latency_p50_ms": round(statistics.median(lat), 3) if lat else None,
                "latency_p95_ms": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 3) if lat else None,
                "rows": rows,
            }

    return {
        "generated": time.time(), "seconds": round(time.time() - t_start, 2), "llm": use_llm,
        "train_scenarios": len(train), "learn_repeats": LEARN_REPEATS,
        "setups": results, "anomaly_points": anomaly_points,
    }
