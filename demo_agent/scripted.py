"""Deterministic stand-in for an LLM agent.

It executes the scenario's plan and, like a prompt-injectable model, obeys
instructions it finds in tool output (the scenario's `hijack` block). This
keeps demos and evaluations reproducible and free; `claude_agent.py` runs the
same tools with a real model.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from agentleash.sdk import GuardedSession

from .sandbox import Sandbox

PLACEHOLDER = re.compile(r"\{\{(\w+)(?::(\w+))?\}\}")


def _render(value, last: str, sb: Sandbox):
    if isinstance(value, dict):
        return {k: _render(v, last, sb) for k, v in value.items()}
    if not isinstance(value, str):
        return value

    def sub(m: re.Match) -> str:
        name, arg = m.group(1), m.group(2)
        if name == "last":
            return last
        if name == "last_urlencoded":
            return quote(last.replace("\n", ";"))
        if name == "customer_email":
            out = sb.query_db(f"SELECT email FROM customers WHERE id={int(arg)}")
            return out.splitlines()[-1]
        return m.group(0)

    return PLACEHOLDER.sub(sub, value)


def run(scenario: dict, session: GuardedSession, sb: Sandbox) -> tuple[str, list]:
    """Returns the final message and the results of the user-requested (non-hijack) steps."""
    last = ""
    planned = []
    hijack = scenario.get("hijack")
    hijacked = False
    for step in scenario["steps"]:
        result = session.call(step["tool"], _render(step.get("args", {}), last, sb))
        planned.append(result)
        if result.ok:
            last = result.output
        if hijack and not hijacked and result.ok and hijack["when_output_contains"] in result.output:
            hijacked = True
            for h in hijack["steps"]:
                r = session.call(h["tool"], _render(h.get("args", {}), last, sb))
                if r.ok:
                    last = r.output
    done = sum(1 for h in session.history if h.ok)
    blocked = sum(1 for h in session.history if not h.ok)
    return f"Finished: {done} tool calls succeeded, {blocked} blocked.", planned
