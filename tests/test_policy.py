from agentleash.gateway import features as F
from agentleash.gateway import policy as P
from agentleash.models import ToolCallEvent

POLICY = P.load("""
agent: test
tools:
  read_file: {allow: true, args: {path: {glob: ["/finance/**"]}}}
  send_email: {allow: true, rate: 2, args: {to: {domain_in: [company.com]}}}
  query_db: {allow: true, args: {sql: {readonly: true, tables_in: [invoices]}}}
  delete_file: {allow: false}
sequences_deny:
  - {after: "read_file:/secrets/**", then: send_email}
""")


def ev(tool, **args):
    return ToolCallEvent(agent_id="test", session_id="s", task="t", tool=tool, args=args)


def codes(event, session=None):
    return [v.code for v in P.evaluate(POLICY, event, session or P.SessionState())]


def test_path_glob_and_traversal():
    assert codes(ev("read_file", path="/finance/reports/q3.txt")) == []
    assert codes(ev("read_file", path="/finance/../secrets/api_keys.env")) == ["path_outside_policy"]
    assert codes(ev("read_file", path="/financeX/a.txt")) == ["path_outside_policy"]


def test_recipient_domain():
    assert codes(ev("send_email", to="cfo@company.com")) == []
    assert codes(ev("send_email", to="cfo@cornpany.com")) == ["recipient_not_allowed"]
    assert codes(ev("send_email", to="a@company.com, b@evil.io")) == ["recipient_not_allowed"]
    assert codes(ev("send_email", to="x@mail.company.com")) == []


def test_sql_rules():
    assert codes(ev("query_db", sql="SELECT * FROM invoices WHERE id='1'")) == []
    assert "sql_not_readonly" in codes(ev("query_db", sql="DELETE FROM invoices"))
    assert codes(ev("query_db", sql="SELECT email FROM customers")) == ["sql_table_not_allowed"]
    assert "sql_not_readonly" in codes(ev("query_db", sql="SELECT 1; DROP TABLE invoices"))


def test_disabled_and_unknown_tools():
    assert codes(ev("delete_file", path="/tmp/x")) == ["tool_not_allowed"]
    assert codes(ev("http_get", url="https://x.io")) == ["tool_not_in_policy"]


def test_rate_limit_and_sequence():
    s = P.SessionState()
    s.record("send_email", {"to": "a@company.com"})
    s.record("send_email", {"to": "a@company.com"})
    assert "rate_limit" in codes(ev("send_email", to="a@company.com"), s)

    s = P.SessionState()
    s.record("read_file", {"path": "/secrets/api_keys.env"})
    assert "forbidden_sequence" in codes(ev("send_email", to="cfo@company.com"), s)


def test_features():
    assert F.path_dir2("/finance/invoices/INV-1.txt") == "/finance/invoices"
    assert F.path_dir2("/finance/vendors.csv") == "/finance"
    assert F.sql_info("UPDATE payments SET x=1 WHERE id=2").ops == {"UPDATE"}
    assert F.resource_keys("send_email", {"to": "a@b.com"}) == ["domain:b.com"]
