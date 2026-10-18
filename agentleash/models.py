"""Shared schemas between the SDK and the gateway."""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

Risk = Literal["low", "medium", "high"]
Verdict = Literal["ALLOW", "DENY", "NEEDS_APPROVAL"]
Mode = Literal["learn", "simulate", "enforce"]


class ToolCallEvent(BaseModel):
    agent_id: str
    session_id: str
    task: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    risk: Risk = "low"
    tainted: bool = False
    taint_sources: list[str] = Field(default_factory=list)
    step: int = 0
    prev_tools: list[str] = Field(default_factory=list)
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = Field(default_factory=time.time)


class AnomalyFactor(BaseModel):
    name: str
    score: float
    detail: str


class Decision(BaseModel):
    event_id: str
    verdict: Verdict
    reasons: list[str] = Field(default_factory=list)
    reason_details: list[str] = Field(default_factory=list)
    anomaly_score: float = 0.0
    anomaly_factors: list[AnomalyFactor] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    explanation: str | None = None
    approval_id: str | None = None
    mode: Mode = "enforce"
    simulated_verdict: Verdict | None = None
    latency_ms: float = 0.0


class ApprovalStatus(BaseModel):
    approval_id: str
    status: Literal["pending", "approved", "denied", "expired"]
    decided_by: str | None = None
