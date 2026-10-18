"""FastAPI app: the gateway API used by the SDK, plus the dashboard and demo-lab endpoints."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import config, llm
from ..models import Decision, ToolCallEvent
from ..sdk import LocalClient
from . import policy as P
from .engine import Engine
from .store import Store

log = logging.getLogger("agentleash.app")

# Imported lazily so the gateway can run without the demo package.
from demo_agent import runner  # noqa: E402
from demo_agent.sandbox import Sandbox  # noqa: E402
from demo_agent.tools import AGENTS  # noqa: E402

app = FastAPI(title="AgentLeash", version="0.1.0")
store = Store(config.DATA_DIR / "gateway.db")
engine = Engine(store)
sandbox = Sandbox(config.SANDBOX_DIR)
client = LocalClient(engine)

runs: dict[str, dict] = {}
run_lock = threading.Lock()
jobs: dict[str, dict] = {"learn": {"status": "idle"}, "eval": {"status": "idle"}}
EVAL_PATH = config.DATA_DIR / "eval_results.json"


def register_agents() -> None:
    for agent_id, desc in AGENTS.items():
        engine.register_agent(agent_id, desc, sandbox.granted_permissions())


register_agents()


# --------------------------------------------------------------- SDK API (v1)
@app.post("/api/v1/authorize", response_model=Decision)
def authorize(event: ToolCallEvent) -> Decision:
    return engine.authorize(event)


@app.get("/api/v1/approvals/{approval_id}")
def approval_status(approval_id: str) -> dict:
    row = engine.approval_status(approval_id)
    if not row:
        raise HTTPException(404, "unknown approval")
    return row


# ----------------------------------------------------------------- dashboard
@app.get("/api/config")
def get_config() -> dict:
    return {"llm": llm.available(), "gateway_model": config.GATEWAY_MODEL, "agent_model": config.AGENT_MODEL,
            "slack": bool(config.SLACK_WEBHOOK_URL), "thresholds": {
                "approval": config.APPROVAL_THRESHOLD, "deny": config.DENY_THRESHOLD}}


@app.get("/api/stats")
def stats() -> dict:
    return engine.stats()


@app.get("/api/timeline")
def timeline(window: int = 3600, buckets: int = 30) -> dict:
    return engine.timeline(buckets=buckets, window_s=window)


@app.get("/api/events")
def events(agent: str | None = None, verdict: str | None = None, limit: int = 200, q: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM events WHERE 1=1", []
    if agent:
        sql += " AND agent_id=?"
        params.append(agent)
    if verdict == "BLOCKED":
        sql += " AND (verdict IN ('DENY','NEEDS_APPROVAL') OR simulated_verdict IN ('DENY','NEEDS_APPROVAL'))"
    elif verdict:
        sql += " AND verdict=?"
        params.append(verdict)
    if q:
        sql += " AND (tool LIKE ? OR task LIKE ? OR args LIKE ?)"
        params += [f"%{q}%"] * 3
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(min(limit, 1000))
    rows = store.query(sql, params)
    approvals = {a["approval_id"]: a["status"] for a in store.query("SELECT approval_id, status FROM approvals")}
    for r in rows:
        r["approval_status"] = approvals.get(r["approval_id"])
    return rows


@app.get("/api/events/{event_id}")
def event_detail(event_id: str) -> dict:
    row = store.one("SELECT * FROM events WHERE event_id=?", (event_id,))
    if not row:
        raise HTTPException(404)
    if row["approval_id"]:
        row["approval"] = engine.approval_status(row["approval_id"])
    return row


@app.get("/api/agents")
def agents() -> list[dict]:
    out = []
    for a in store.query("SELECT * FROM agents ORDER BY agent_id"):
        aid = a["agent_id"]
        versions = engine.policy_versions(aid)
        counts = store.one(
            "SELECT COUNT(*) AS n, SUM(verdict='DENY') AS deny, SUM(verdict='NEEDS_APPROVAL') AS held, "
            "SUM(simulated_verdict IN ('DENY','NEEDS_APPROVAL')) AS sim FROM events WHERE agent_id=?", (aid,))
        tools = store.query("SELECT tool, COUNT(*) AS n FROM events WHERE agent_id=? AND verdict='ALLOW' "
                            "GROUP BY tool ORDER BY n DESC", (aid,))
        perms = engine.permissions(aid)
        out.append({
            "agent_id": aid, "description": a["description"], "mode": a["mode"],
            "policy_version": versions[0]["version"] if versions else None,
            "policy_source": versions[0]["source"] if versions else None,
            "events": counts["n"] or 0, "denied": counts["deny"] or 0, "held": counts["held"] or 0,
            "simulated_blocks": counts["sim"] or 0, "tools": tools,
            "granted": len(perms["granted"]), "used": len(perms["used"]), "used_list": perms["used"],
            "unused_list": perms["unused"], "baseline": engine.baseline(aid).summary(),
        })
    return out


class ModeBody(BaseModel):
    mode: str


@app.post("/api/agents/{agent_id}/mode")
def set_mode(agent_id: str, body: ModeBody) -> dict:
    try:
        engine.set_mode(agent_id, body.mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@app.post("/api/agents/{agent_id}/generate-policy")
def generate_policy(agent_id: str) -> dict:
    try:
        return engine.generate_policy(agent_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/agents/{agent_id}/policy")
def get_policy(agent_id: str) -> dict:
    versions = engine.policy_versions(agent_id)
    return {"current": versions[0] if versions else None, "versions": versions}


class PolicyBody(BaseModel):
    yaml: str


@app.put("/api/agents/{agent_id}/policy")
def put_policy(agent_id: str, body: PolicyBody) -> dict:
    try:
        return engine.save_policy(agent_id, body.yaml, source="manual")
    except P.PolicyError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/agents/{agent_id}/replay")
def replay(agent_id: str, body: PolicyBody | None = None) -> dict:
    try:
        return engine.replay(agent_id, body.yaml if body and body.yaml.strip() else None)
    except P.PolicyError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/approvals")
def approvals() -> dict:
    recent = store.query(
        "SELECT a.*, e.tool, e.args, e.task, e.explanation FROM approvals a JOIN events e ON e.event_id=a.event_id "
        "WHERE a.status!='pending' ORDER BY a.decided DESC LIMIT 30")
    return {"pending": engine.pending_approvals(), "recent": recent}


class ApprovalBody(BaseModel):
    approve: bool


@app.post("/api/approvals/{approval_id}")
def decide(approval_id: str, body: ApprovalBody) -> dict:
    try:
        return engine.decide_approval(approval_id, body.approve, by="dashboard")
    except KeyError:
        raise HTTPException(404, "unknown approval")


@app.get("/api/audit")
def audit(limit: int = 150) -> dict:
    return {"verify": engine.audit.verify(), "rows": engine.audit.tail(limit)}


@app.post("/api/audit/tamper")
def tamper() -> dict:
    res = engine.audit.tamper()
    if not res:
        raise HTTPException(400, "audit log is empty")
    return {**res, "verify": engine.audit.verify()}


# ------------------------------------------------------------------ demo lab
@app.get("/api/scenarios")
def get_scenarios() -> dict:
    return runner.scenarios()


@app.get("/api/sandbox")
def sandbox_state() -> dict:
    return sandbox.state()


@app.post("/api/sandbox/reset")
def sandbox_reset() -> dict:
    with run_lock:
        sandbox.reset()
    return sandbox.state()


class RunBody(BaseModel):
    scenario_id: str | None = None
    task: str | None = None
    agent: str = "finance-assistant"
    protected: bool = True
    agent_mode: str = "scripted"
    reset: bool = True


def _run_job(run_id: str, scenario: dict, body: RunBody) -> None:
    rec = runs[run_id]

    def on_step(result) -> None:
        rec["steps"].append(runner.step_view(result))

    with run_lock:
        rec["status"] = "running"
        try:
            if body.reset:
                sandbox.reset()
            result = runner.run(scenario, sandbox, client if body.protected else None, body.agent_mode, on_step=on_step)
            rec.update(result, status="done")
        except Exception as exc:  # surface failures in the UI instead of a silent thread death
            log.exception("run failed")
            rec.update(status="error", error=str(exc))


@app.post("/api/lab/run")
def lab_run(body: RunBody) -> dict:
    if body.scenario_id:
        try:
            scenario = dict(runner.find(body.scenario_id))
        except KeyError:
            raise HTTPException(404, "unknown scenario")
    elif body.task:
        if body.agent_mode != "claude":
            raise HTTPException(400, "free-text tasks need the Claude agent (set ANTHROPIC_API_KEY)")
        scenario = {"id": "custom", "agent": body.agent, "task": body.task, "steps": [], "kind": "custom"}
    else:
        raise HTTPException(400, "give a scenario_id or a task")
    if body.agent_mode == "claude" and not llm.available():
        raise HTTPException(400, "Claude agent needs ANTHROPIC_API_KEY (or `ant auth login`)")
    run_id = uuid.uuid4().hex[:10]
    runs[run_id] = {"run_id": run_id, "status": "queued", "steps": [], "scenario": scenario.get("id"),
                    "task": scenario["task"], "agent": scenario["agent"], "protected": body.protected,
                    "kind": scenario.get("kind"), "name": scenario.get("name"), "started": time.time()}
    threading.Thread(target=_run_job, args=(run_id, scenario, body), daemon=True).start()
    return runs[run_id]


@app.get("/api/lab/runs/{run_id}")
def lab_run_status(run_id: str) -> dict:
    if run_id not in runs:
        raise HTTPException(404)
    return runs[run_id]


def _learn_job() -> None:
    job = jobs["learn"]
    train = [s for s in runner.scenarios()["benign"] if s["split"] == "train"]
    with run_lock:
        try:
            for agent_id in AGENTS:
                engine.set_mode(agent_id, "learn")
            for i, s in enumerate(train * 2):
                sandbox.reset()
                runner.run(s, sandbox, client)
                job["progress"] = (i + 1) / (len(train) * 2)
                job["message"] = f"learning from: {s['task']}"
            sandbox.reset()
            if job.get("enforce"):
                for agent_id in AGENTS:
                    engine.generate_policy(agent_id)
                    engine.set_mode(agent_id, "enforce")
            job.update(status="done", message="learning complete")
        except Exception as exc:
            log.exception("learning failed")
            job.update(status="error", message=str(exc))


@app.post("/api/lab/learn")
def lab_learn(enforce: bool = Body(False, embed=True)) -> dict:
    if jobs["learn"].get("status") == "running":
        raise HTTPException(409, "learning already running")
    jobs["learn"] = {"status": "running", "progress": 0.0, "enforce": enforce, "message": "starting"}
    threading.Thread(target=_learn_job, daemon=True).start()
    return jobs["learn"]


@app.get("/api/lab/learn")
def lab_learn_status() -> dict:
    return jobs["learn"]


@app.post("/api/demo/reset")
def demo_reset() -> dict:
    with run_lock:
        store.reset()
        engine._policies.clear()
        engine._baselines.clear()
        engine.reset_sessions()
        sandbox.reset()
        runs.clear()
        register_agents()
    return {"ok": True}


# ---------------------------------------------------------------- evaluation
def _eval_job(use_llm: bool) -> None:
    from evaluation.harness import run_eval

    job = jobs["eval"]

    def progress(msg: str, frac: float) -> None:
        job.update(message=msg, progress=frac)

    try:
        result = run_eval(use_llm=use_llm, progress=progress)
        EVAL_PATH.write_text(json.dumps(result))
        job.update(status="done", message="evaluation complete", progress=1.0)
    except Exception as exc:
        log.exception("eval failed")
        job.update(status="error", message=str(exc))


@app.post("/api/eval/run")
def eval_run(use_llm: bool = Body(False, embed=True)) -> dict:
    if jobs["eval"].get("status") == "running":
        raise HTTPException(409, "evaluation already running")
    jobs["eval"] = {"status": "running", "progress": 0.0, "message": "starting"}
    threading.Thread(target=_eval_job, args=(use_llm and llm.available(),), daemon=True).start()
    return jobs["eval"]


@app.get("/api/eval")
def eval_results() -> dict[str, Any]:
    results = json.loads(EVAL_PATH.read_text()) if EVAL_PATH.exists() else None
    return {"job": jobs["eval"], "results": results}


# ------------------------------------------------------------------- static
@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.DASHBOARD_DIR / "index.html")


app.mount("/", StaticFiles(directory=config.DASHBOARD_DIR), name="dashboard")
