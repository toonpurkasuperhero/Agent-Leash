"""End-to-end: learn from benign scenarios, then check attacks are stopped and normal work flows."""
import pytest

from agentleash.gateway.engine import Engine
from agentleash.gateway.store import Store
from agentleash.sdk import LocalClient
from demo_agent import runner
from demo_agent.sandbox import Sandbox
from demo_agent.tools import AGENTS


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("al")
    sb = Sandbox(tmp / "sandbox")
    engine = Engine(Store(tmp / "gw.db"), use_llm=False, notify=False)
    for aid, desc in AGENTS.items():
        engine.register_agent(aid, desc, sb.granted_permissions())
    client = LocalClient(engine)
    train = [s for s in runner.scenarios()["benign"] if s["split"] == "train"]
    for s in train:
        sb.reset()
        runner.run(s, sb, client)
    for aid in AGENTS:
        engine.generate_policy(aid)
        engine.set_mode(aid, "enforce")
    return engine, sb, client


def run(env, sid, approve=False):
    engine, sb, client = env
    sb.reset()
    engine.reset_sessions()
    engine.approval_oracle = lambda ev, d: approve
    return runner.run(runner.find(sid), sb, client, approval_timeout=0)


@pytest.mark.parametrize("sid", [s["id"] for s in runner.scenarios()["attacks"]])
def test_attacks_cause_no_damage(env, sid):
    assert run(env, sid)["damage"] == []


def test_attacks_damage_without_protection(env):
    _, sb, _ = env
    sb.reset()
    r = runner.run(runner.find("A01"), sb, None)
    assert any(d["kind"] == "data_exfiltration" for d in r["damage"])


@pytest.mark.parametrize("sid", ["FT1", "FT2", "FT3", "FT4", "FT5", "FT7", "ST1", "ST2", "ST3"])
def test_benign_tasks_complete(env, sid):
    r = run(env, sid, approve=True)
    assert r["completed"] and not r["damage"]


def test_new_external_recipient_is_blocked(env):
    r = run(env, "FT6", approve=True)
    assert not r["completed"]
    assert "recipient_not_allowed" in r["steps"][-1]["reasons"]


def test_audit_chain_detects_tampering(env):
    engine, _, _ = env
    assert engine.audit.verify()["ok"]
    engine.audit.tamper()
    assert not engine.audit.verify()["ok"]


def test_simulate_mode_never_blocks(env):
    engine, sb, client = env
    engine.set_mode("finance-assistant", "simulate")
    try:
        sb.reset()
        engine.reset_sessions()
        r = runner.run(runner.find("A05"), sb, client)
        assert r["damage"]  # simulate observes only
        assert any(s["verdict"] == "DENY" for s in r["steps"])
    finally:
        engine.set_mode("finance-assistant", "enforce")
