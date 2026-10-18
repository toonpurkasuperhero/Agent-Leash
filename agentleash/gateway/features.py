"""Turn raw tool-call arguments into the resource features that policies,
the anomaly scorer and the learner all reason about."""
from __future__ import annotations

import fnmatch
import posixpath
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import sqlglot
from sqlglot import exp

PATH_TOOLS = {"read_file", "list_files", "write_file", "delete_file"}
EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")

_SQL_OPS = {
    exp.Select: "SELECT",
    exp.Insert: "INSERT",
    exp.Update: "UPDATE",
    exp.Delete: "DELETE",
    exp.Drop: "DROP",
    exp.Create: "CREATE",
    exp.Alter: "ALTER",
}


def norm_path(path: str) -> str:
    p = posixpath.normpath("/" + str(path or "").strip().lstrip("/"))
    return "/" if p in (".", "") else p


def path_top(path: str) -> str:
    parts = [p for p in norm_path(path).split("/") if p]
    return "/" + parts[0] if parts else "/"


def path_dir2(path: str) -> str:
    """First two directory levels; a trailing file name (anything with a dot) is dropped."""
    parts = [p for p in norm_path(path).split("/") if p]
    if parts and "." in parts[-1]:
        parts = parts[:-1]
    if len(parts) <= 1:
        return "/" + "/".join(parts)
    return "/" + "/".join(parts[:2])


def glob_match(path: str, pattern: str) -> bool:
    p = norm_path(path)
    if pattern.endswith("/**"):
        base = pattern[:-3] or "/"
        return p == base or p.startswith(base.rstrip("/") + "/")
    return fnmatch.fnmatchcase(p, pattern)


def email_domains(value: str) -> list[str]:
    return [d.lower() for d in EMAIL_RE.findall(str(value or ""))]


def url_host(url: str) -> str:
    return (urlparse(str(url or "")).hostname or "").lower()


def domain_matches(domain: str, allowed: str) -> bool:
    domain, allowed = domain.lower(), allowed.lower()
    return domain == allowed or domain.endswith("." + allowed)


@dataclass
class SqlInfo:
    ops: set[str] = field(default_factory=set)
    tables: set[str] = field(default_factory=set)
    has_where: bool = False
    parse_error: bool = False

    @property
    def readonly(self) -> bool:
        return bool(self.ops) and self.ops <= {"SELECT"} and not self.parse_error


def sql_info(sql: str) -> SqlInfo:
    info = SqlInfo()
    try:
        statements = [s for s in sqlglot.parse(str(sql or ""), read="sqlite") if s is not None]
    except Exception:
        info.parse_error = True
        first = (str(sql or "").strip().split() or ["OTHER"])[0].upper()
        info.ops.add(first)
        return info
    for stmt in statements:
        op = next((name for cls, name in _SQL_OPS.items() if isinstance(stmt, cls)), "OTHER")
        info.ops.add(op)
        for table in stmt.find_all(exp.Table):
            if table.name:
                info.tables.add(table.name.lower())
        if stmt.find(exp.Where) is not None:
            info.has_where = True
    if not statements:
        info.parse_error = True
    return info


def resource_keys(tool: str, args: dict) -> list[str]:
    """Coarse resource identifiers, e.g. 'dir:/finance', 'domain:company.com', 'sql:SELECT:customers'."""
    if tool in PATH_TOOLS:
        return [f"dir:{path_dir2(args.get('path', '/'))}"]
    if tool == "send_email":
        return [f"domain:{d}" for d in email_domains(args.get("to", ""))] or ["domain:?"]
    if tool == "http_get":
        return [f"host:{url_host(args.get('url', ''))}"]
    if tool == "query_db":
        info = sql_info(args.get("sql", ""))
        return [f"sql:{op}:{t}" for op in sorted(info.ops) for t in sorted(info.tables or {"?"})]
    return [f"tool:{tool}"]


def permission_keys(tool: str, args: dict) -> list[str]:
    """The coarse grant a call exercises - comparable with an agent's granted inventory."""
    if tool in PATH_TOOLS:
        return [f"{tool}:{path_top(args.get('path', '/'))}"]
    if tool == "query_db":
        info = sql_info(args.get("sql", ""))
        return [f"query_db:{op}:{t}" for op in sorted(info.ops) for t in sorted(info.tables or {"?"})]
    if tool in ("send_email", "http_get"):
        return [f"{tool}:*"]
    return [tool]


def payload_size(args: dict) -> int:
    return sum(len(str(v)) for v in args.values())
