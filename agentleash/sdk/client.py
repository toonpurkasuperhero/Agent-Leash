"""Transports from the SDK to the gateway: in-process or over HTTP."""
from __future__ import annotations

import time
from typing import Protocol

import httpx

from ..models import Decision, ToolCallEvent


class GatewayClient(Protocol):
    def authorize(self, event: ToolCallEvent) -> Decision: ...
    def wait_for_approval(self, approval_id: str, timeout: float) -> str: ...


class LocalClient:
    """Calls an Engine in the same process (used by the dashboard's demo runner and the eval harness)."""

    def __init__(self, engine):
        self.engine = engine

    def authorize(self, event: ToolCallEvent) -> Decision:
        return self.engine.authorize(event)

    def wait_for_approval(self, approval_id: str, timeout: float) -> str:
        return self.engine.wait_for_approval(approval_id, timeout)


class HttpClient:
    """Calls a remote AgentLeash gateway, e.g. `HttpClient("http://localhost:8000")`."""

    def __init__(self, base_url: str, timeout: float = 10.0, api_key: str | None = None):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, headers=headers)

    def authorize(self, event: ToolCallEvent) -> Decision:
        r = self.http.post("/api/v1/authorize", json=event.model_dump())
        r.raise_for_status()
        return Decision.model_validate(r.json())

    def wait_for_approval(self, approval_id: str, timeout: float) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = self.http.get(f"/api/v1/approvals/{approval_id}")
            r.raise_for_status()
            status = r.json()["status"]
            if status != "pending":
                return status
            time.sleep(0.5)
        return "expired"
