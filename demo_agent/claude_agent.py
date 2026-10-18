"""A real Claude agent whose every tool call goes through AgentLeash."""
from __future__ import annotations

import anthropic

from agentleash import config
from agentleash.sdk import GuardedSession

SYSTEM = {
    "finance-assistant": (
        "You are the finance team's assistant at company.com. You can read the shared file system, the "
        "production database, the shared inbox and the web, and send email. Complete the user's request "
        "with the tools, then reply with a short summary."
    ),
    "support-bot": (
        "You are a customer-support agent at company.com. Use the tickets and customers tables to help "
        "customers and reply by email. Complete the user's request, then reply with a short summary."
    ),
}
MAX_TURNS = 12


def run(task: str, session: GuardedSession, agent_id: str) -> str:
    client = anthropic.Anthropic()
    tools = [{"name": s.name, "description": s.description, "input_schema": s.input_schema}
             for s in session.tools.values()]
    messages = [{"role": "user", "content": task}]
    for _ in range(MAX_TURNS):
        params = dict(model=config.AGENT_MODEL, max_tokens=16000, system=SYSTEM.get(agent_id, SYSTEM["finance-assistant"]),
                      tools=tools, messages=messages, output_config={"effort": "low"})
        try:
            response = client.beta.messages.create(**params, betas=["server-side-fallback-2026-07-01"],
                                                   extra_body={"fallbacks": "default"})
        except anthropic.BadRequestError:
            response = client.messages.create(**params)

        if response.stop_reason == "refusal":
            return "The model declined this request."
        messages.append({"role": "assistant", "content": response.content})
        uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not uses:
            return "".join(b.text for b in response.content if b.type == "text").strip() or "(no reply)"

        results = []
        for block in uses:
            r = session.call(block.name, dict(block.input or {}))
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": r.output[:8000],
                            "is_error": not r.ok})
        messages.append({"role": "user", "content": results})
    return "Stopped after the maximum number of turns."
