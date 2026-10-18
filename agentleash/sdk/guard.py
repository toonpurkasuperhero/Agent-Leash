"""Wrap an agent's tools so every call is authorized by the gateway first.

    session = GuardedSession(client, agent_id="finance-assistant", task=user_request, tools=TOOLS)
    result = session.call("send_email", {"to": "...", "subject": "...", "body": "..."})
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from ..models import Decision, Risk, ToolCallEvent
from .client import GatewayClient

log = logging.getLogger("agentleash.sdk")

# A taint function inspects a call and its output and returns the untrusted
# sources it introduced (e.g. ["email:vendor@external.com"]), or [] if none.
TaintFn = Callable[[dict, str], list[str]]


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., str]
    risk: Risk = "low"
    description: str = ""
    input_schema: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    taint: TaintFn | None = None


@dataclass
class CallResult:
    tool: str
    args: dict
    ok: bool
    output: str
    decision: Decision | None = None
    approval: str | None = None  # approved / denied / expired

    @property
    def blocked(self) -> bool:
        return not self.ok and self.decision is not None


class GuardedSession:
    def __init__(self, client: GatewayClient | None, agent_id: str, task: str, tools: dict[str, ToolSpec],
                 approval_timeout: float = 120.0, on_step: Callable[[CallResult], None] | None = None,
                 session_id: str | None = None):
        self.client = client  # None = unprotected (no gateway)
        self.agent_id = agent_id
        self.task = task
        self.tools = tools
        self.approval_timeout = approval_timeout
        self.on_step = on_step
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.taint_sources: list[str] = []
        self.history: list[CallResult] = []

    def _emit(self, result: CallResult) -> CallResult:
        self.history.append(result)
        if self.on_step:
            self.on_step(result)
        return result

    def call(self, name: str, args: dict[str, Any]) -> CallResult:
        spec = self.tools.get(name)
        if spec is None:
            return self._emit(CallResult(name, args, False, f"Error: unknown tool {name}"))

        decision = None
        approval = None
        if self.client is not None:
            event = ToolCallEvent(
                agent_id=self.agent_id, session_id=self.session_id, task=self.task, tool=name, args=args,
                risk=spec.risk, tainted=bool(self.taint_sources), taint_sources=list(self.taint_sources),
                step=len(self.history), prev_tools=[h.tool for h in self.history if h.ok][-5:],
            )
            try:
                decision = self.client.authorize(event)
            except Exception as exc:  # fail closed for anything that can do damage
                log.warning("gateway unreachable: %s", exc)
                if spec.risk != "low":
                    decision = Decision(event_id=event.event_id, verdict="DENY", reasons=["gateway_unreachable"],
                                        explanation="AgentLeash gateway unreachable; failing closed.")
            if decision is not None and decision.verdict == "NEEDS_APPROVAL":
                approval = self.client.wait_for_approval(decision.approval_id, self.approval_timeout)
                if approval != "approved":
                    return self._emit(CallResult(name, args, False,
                                                 f"Blocked by AgentLeash: a human reviewer {approval} this action. "
                                                 f"{decision.explanation or ''}".strip(), decision, approval))
            elif decision is not None and decision.verdict == "DENY":
                return self._emit(CallResult(name, args, False,
                                             f"Blocked by AgentLeash: {decision.explanation or ', '.join(decision.reasons)}",
                                             decision))

        try:
            output = str(spec.fn(**args))
        except Exception as exc:
            return self._emit(CallResult(name, args, False, f"Error: {exc}", decision, approval))
        if spec.taint:
            for src in spec.taint(args, output):
                if src not in self.taint_sources:
                    self.taint_sources.append(src)
        return self._emit(CallResult(name, args, True, output, decision, approval))
