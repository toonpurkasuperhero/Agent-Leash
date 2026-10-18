"""Runtime configuration, read from environment variables."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("AGENTLEASH_DATA_DIR", ROOT / "data"))
SANDBOX_DIR = Path(os.getenv("AGENTLEASH_SANDBOX_DIR", ROOT / "sandbox"))
DASHBOARD_DIR = ROOT / "dashboard"
SCENARIO_DIR = ROOT / "scenarios"

# "auto" uses Claude when credentials are present, "off" forces the
# deterministic fallbacks (useful for offline demos and reproducible evals).
LLM_MODE = os.getenv("AGENTLEASH_LLM", "auto")
GATEWAY_MODEL = os.getenv("AGENTLEASH_GATEWAY_MODEL", "claude-haiku-5-5")
AGENT_MODEL = os.getenv("AGENTLEASH_AGENT_MODEL", "claude-opus-5-5")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
DASHBOARD_URL = os.getenv("AGENTLEASH_DASHBOARD_URL", "http://localhost:8000")

APPROVAL_THRESHOLD = float(os.getenv("AGENTLEASH_APPROVAL_THRESHOLD", "0.6"))
DENY_THRESHOLD = float(os.getenv("AGENTLEASH_DENY_THRESHOLD", "0.9"))
APPROVAL_TIMEOUT_S = float(os.getenv("AGENTLEASH_APPROVAL_TIMEOUT", "120"))

INTERNAL_DOMAINS = {"company.com"}
