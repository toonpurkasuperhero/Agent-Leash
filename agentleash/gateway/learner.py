"""Generate a least-privilege policy from what an agent actually did in learn mode."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .. import config
from . import features as F

# Sensitive sources and outbound sinks: data from the former never flows to the latter.
DEFAULT_SEQUENCES = [
    {"after": "read_file:/secrets/**", "then": "send_email", "reason": "secrets read earlier in the session cannot be emailed"},
    {"after": "read_file:/secrets/**", "then": "http_get", "reason": "secrets read earlier in the session cannot leave via HTTP"},
    {"after": "read_file:/hr/**", "then": "send_email:external", "reason": "HR data cannot be emailed outside the company"},
    {"after": "query_db", "then": "http_get:external", "reason": "database results cannot be sent to external hosts"},
]


def _path_globs(paths: list[str]) -> list[str]:
    """Generalise observed paths to the narrowest sensible folder globs."""
    by_top: dict[str, set[str]] = defaultdict(set)
    for p in paths:
        by_top[F.path_top(p)].add(F.path_dir2(p))
    globs = []
    for top, dirs in sorted(by_top.items()):
        sub = {d for d in dirs if d != top}
        if top == "/" or len(sub) != 1 or top in dirs:
            globs.append(f"{top.rstrip('/')}/**" if top != "/" else "/**")
        else:
            globs.append(f"{next(iter(sub))}/**")
    return globs


def generate(agent_id: str, rows: list[dict]) -> dict[str, Any]:
    by_tool: dict[str, list[dict]] = defaultdict(list)
    per_session: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_tool[row["tool"]].append(row["args"] or {})
        per_session[row["session_id"]][row["tool"]] += 1

    def rate(tool: str) -> int:
        peak = max((c[tool] for c in per_session.values()), default=0)
        return max(3, peak * 2)

    tools: dict[str, Any] = {}
    for tool, calls in sorted(by_tool.items()):
        rule: dict[str, Any] = {"allow": True, "rate": rate(tool)}
        args: dict[str, Any] = {}
        if tool in F.PATH_TOOLS:
            args["path"] = {"glob": _path_globs([c.get("path", "/") for c in calls])}
        elif tool == "send_email":
            domains = sorted({d for c in calls for d in F.email_domains(c.get("to", ""))})
            args["to"] = {"domain_in": domains or sorted(config.INTERNAL_DOMAINS)}
        elif tool == "http_get":
            args["url"] = {"host_in": sorted({F.url_host(c.get("url", "")) for c in calls} - {""})}
        elif tool == "query_db":
            infos = [F.sql_info(c.get("sql", "")) for c in calls]
            ops = sorted(set().union(*(i.ops for i in infos)))
            sql: dict[str, Any] = {"tables_in": sorted(set().union(*(i.tables for i in infos)))}
            if ops == ["SELECT"]:
                sql["readonly"] = True
            else:
                sql["ops_in"] = ops
                sql["require_where_for_writes"] = True
            args["sql"] = sql
        if args:
            rule["args"] = args
        tools[tool] = rule

    return {
        "agent": agent_id,
        "generated_from": {"events": len(rows), "sessions": len(per_session)},
        "tools": tools,
        "sequences_deny": DEFAULT_SEQUENCES,
        "taint": {"high_risk_requires_approval": True, "mode": "novel"},
    }
