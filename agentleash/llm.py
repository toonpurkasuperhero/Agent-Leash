"""Thin wrapper around the Anthropic SDK used by the gateway's AI components.

Every caller has a deterministic fallback, so the gateway keeps working (and
stays fast) when no credentials are configured or the API is unreachable.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from . import config

log = logging.getLogger("agentleash.llm")
_client = None


def available() -> bool:
    if config.LLM_MODE == "off":
        return False
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return True
    # `ant auth login` profiles are picked up by the zero-arg client.
    return (Path.home() / ".config" / "anthropic").exists()


def client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(timeout=15.0, max_retries=1)
    return _client


def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def complete_json(system: str, prompt: str, schema: dict[str, Any]) -> dict | None:
    """Single structured-output call on the gateway model. Returns None on any failure."""
    if not available():
        return None
    import anthropic

    try:
        response = client().messages.create(
            model=config.GATEWAY_MODEL,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            return None
        return json.loads(_text(response))
    except (anthropic.APIError, json.JSONDecodeError) as exc:
        log.warning("structured LLM call failed: %s", exc)
        return None


def complete_text(system: str, prompt: str, max_tokens: int = 1024) -> str | None:
    if not available():
        return None
    import anthropic

    try:
        response = client().messages.create(
            model=config.GATEWAY_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": "low"},
        )
        if response.stop_reason == "refusal":
            return None
        return _text(response) or None
    except anthropic.APIError as exc:
        log.warning("LLM call failed: %s", exc)
        return None
