"""Tool definitions for the demo agents, bound to a Sandbox instance."""
from __future__ import annotations

from urllib.parse import urlparse

from agentleash.sdk import ToolSpec

from .sandbox import INTERNAL, UNTRUSTED_FILE_PREFIXES, Sandbox

AGENTS = {
    "finance-assistant": "Finance team assistant: invoices, reports, month-end close and email.",
    "support-bot": "Customer-support agent: tickets, customer lookups and replies.",
}


def _schema(props: dict[str, str], required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
        "required": required if required is not None else list(props),
        "additionalProperties": False,
    }


def build_tools(sb: Sandbox) -> dict[str, ToolSpec]:
    def inbox_taint(args, output):
        return [f"email:{s}" for s in sb.inbox_senders() if not s.endswith("@" + INTERNAL)]

    def web_taint(args, output):
        host = urlparse(args.get("url", "")).hostname or ""
        return [] if host.endswith(INTERNAL) else [f"web:{host}"]

    def file_taint(args, output):
        path = "/" + str(args.get("path", "")).lstrip("/")
        return [f"document:{path}"] if path.startswith(UNTRUSTED_FILE_PREFIXES) else []

    def db_taint(args, output):
        # Ticket bodies are written by customers, i.e. untrusted input.
        return ["ticket:a customer-written support ticket"] if "tickets" in str(args.get("sql", "")).lower() and "body" in output.lower() else []

    specs = [
        ToolSpec("list_files", sb.list_files, "low", "List a folder in the company file share.",
                 _schema({"path": "Folder path, e.g. /finance"})),
        ToolSpec("read_file", sb.read_file, "low", "Read a file from the company file share.",
                 _schema({"path": "File path, e.g. /finance/reports/q3_summary.txt"}), file_taint),
        ToolSpec("write_file", sb.write_file, "medium", "Create or overwrite a file.",
                 _schema({"path": "File path", "content": "Full file content"})),
        ToolSpec("delete_file", sb.delete_file, "high", "Delete a file or folder.",
                 _schema({"path": "Path to delete"})),
        ToolSpec("query_db", sb.query_db, "medium",
                 "Run SQL on the production database (tables: customers, invoices, payments, tickets).",
                 _schema({"sql": "A single SQLite statement"}), db_taint),
        ToolSpec("send_email", sb.send_email, "high", "Send an email.",
                 _schema({"to": "Recipient address(es)", "subject": "Subject", "body": "Body"})),
        ToolSpec("http_get", sb.http_get, "medium", "Fetch a URL.", _schema({"url": "Absolute URL"}), web_taint),
        ToolSpec("read_inbox", sb.read_inbox, "low", "Read the shared finance inbox.", _schema({}, []), inbox_taint),
    ]
    return {s.name: s for s in specs}
