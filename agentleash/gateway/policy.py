"""YAML least-privilege policy: parsing, validation and evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

from .. import config
from ..models import ToolCallEvent
from . import features as F


@dataclass
class Violation:
    code: str
    detail: str


@dataclass
class SessionState:
    """What the gateway remembers about one agent session."""

    calls: list[tuple[str, dict]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    scope: list[str] | None = None
    scope_sql_write: bool = False

    def record(self, tool: str, args: dict) -> None:
        self.calls.append((tool, args))
        self.counts[tool] = self.counts.get(tool, 0) + 1


class PolicyError(ValueError):
    pass


def load(text: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise PolicyError(f"Invalid YAML: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("tools", {}), dict):
        raise PolicyError("Policy must be a mapping with a 'tools' mapping")
    for name, rule in data.get("tools", {}).items():
        if not isinstance(rule, dict) or "allow" not in rule:
            raise PolicyError(f"Tool '{name}' needs an 'allow' field")
    for seq in data.get("sequences_deny", []) or []:
        if not isinstance(seq, dict) or "after" not in seq or "then" not in seq:
            raise PolicyError("Each sequences_deny entry needs 'after' and 'then'")
    return data


def dump(policy: dict[str, Any]) -> str:
    return yaml.safe_dump(policy, sort_keys=False, default_flow_style=None, width=100)


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _is_internal(domain: str) -> bool:
    return any(F.domain_matches(domain, d) for d in config.INTERNAL_DOMAINS)


def matches_pattern(pattern: str, tool: str, args: dict) -> bool:
    name, _, qualifier = pattern.partition(":")
    if name != tool:
        return False
    if not qualifier:
        return True
    if qualifier.startswith("/"):
        return F.glob_match(args.get("path", ""), qualifier)
    if qualifier == "external":
        if tool == "send_email":
            return any(not _is_internal(d) for d in F.email_domains(args.get("to", "")))
        if tool == "http_get":
            return not _is_internal(F.url_host(args.get("url", "")))
    if qualifier == "write" and tool == "query_db":
        return not F.sql_info(args.get("sql", "")).readonly
    return False


def _check_args(tool: str, rule: dict, args: dict) -> list[Violation]:
    out: list[Violation] = []
    constraints = rule.get("args") or {}

    path_rule = constraints.get("path")
    if path_rule and "glob" in path_rule:
        path = F.norm_path(args.get("path", "/"))
        globs = _as_list(path_rule["glob"])
        if not any(F.glob_match(path, g) for g in globs):
            out.append(Violation("path_outside_policy", f"{path} is outside {', '.join(globs)}"))

    to_rule = constraints.get("to")
    if to_rule and "domain_in" in to_rule:
        allowed = _as_list(to_rule["domain_in"])
        domains = F.email_domains(args.get("to", ""))
        bad = [d for d in domains if not any(F.domain_matches(d, a) for a in allowed)]
        if bad or not domains:
            out.append(Violation(
                "recipient_not_allowed",
                f"recipient domain {', '.join(bad) or '(none)'} not in {', '.join(allowed)}",
            ))

    url_rule = constraints.get("url")
    if url_rule and "host_in" in url_rule:
        allowed = _as_list(url_rule["host_in"])
        host = F.url_host(args.get("url", ""))
        if not any(F.domain_matches(host, a) for a in allowed):
            out.append(Violation("host_not_allowed", f"host {host or '(none)'} not in {', '.join(allowed)}"))

    sql_rule = constraints.get("sql")
    if sql_rule:
        info = F.sql_info(args.get("sql", ""))
        if sql_rule.get("readonly") and not info.readonly:
            out.append(Violation("sql_not_readonly", f"statement type {', '.join(sorted(info.ops))} on a read-only grant"))
        allowed_ops = _as_list(sql_rule.get("ops_in"))
        if allowed_ops and not info.ops <= set(allowed_ops):
            out.append(Violation("sql_op_not_allowed", f"{', '.join(sorted(info.ops - set(allowed_ops)))} not in {', '.join(allowed_ops)}"))
        tables = _as_list(sql_rule.get("tables_in"))
        if tables and not info.tables <= set(tables):
            out.append(Violation("sql_table_not_allowed", f"table {', '.join(sorted(info.tables - set(tables)))} not in {', '.join(tables)}"))
        if sql_rule.get("require_where_for_writes") and not info.readonly and not info.has_where and info.ops & {"UPDATE", "DELETE"}:
            out.append(Violation("sql_unbounded_write", "UPDATE/DELETE without a WHERE clause"))
    return out


def evaluate(policy: dict[str, Any], event: ToolCallEvent, session: SessionState) -> list[Violation]:
    tools = policy.get("tools", {})
    rule = tools.get(event.tool)
    if rule is None:
        return [Violation("tool_not_in_policy", f"{event.tool} was never granted to this agent")]
    if not rule.get("allow"):
        return [Violation("tool_not_allowed", f"{event.tool} is disabled for this agent")]

    out = _check_args(event.tool, rule, event.args)

    limit = rule.get("rate")
    if limit is not None and session.counts.get(event.tool, 0) + 1 > int(limit):
        out.append(Violation("rate_limit", f"{event.tool} called {session.counts.get(event.tool, 0) + 1}x in one session (limit {limit})"))

    for seq in policy.get("sequences_deny", []) or []:
        if matches_pattern(seq["then"], event.tool, event.args) and any(
            matches_pattern(seq["after"], t, a) for t, a in session.calls
        ):
            out.append(Violation("forbidden_sequence", seq.get("reason") or f"{seq['after']} followed by {seq['then']}"))
    return out
