"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

- Model: gpt-5.6-luna through the Portkey gateway (PORTKEY_API_KEY from .env).
- Shop facts and actions: ONLY through the campus-customs MCP server (mcp_server/server.py).
  Each agent sees just the MCP tools its role needs (least privilege).
- Full connectivity: every agent has a `delegate` tool that can hand a task to any
  other agent. Cycles are blocked (an agent can't be asked by someone it already
  asked) and chains are capped at MAX_DEPTH.
- Every agent-loop step is appended to output/audit_trail.json (see audit.py).
"""

import os
import sys
from functools import partial
from pathlib import Path
from typing import get_args

from dotenv import load_dotenv
from fastmcp.client.transports import PythonStdioTransport
from pydantic_ai import Agent, RunContext, UsageLimits
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage

from audit import log_event
from models import AgentName, AgentReport, TeamDeps, TicketDecision

BACKEND_DIR = Path(__file__).resolve().parent
HW_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
SERVER_PATH = HW_DIR / "mcp_server" / "server.py"

MODEL_NAME = "gpt-5.6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")

# Token and loop guardrails. One shared RunUsage per ticket covers the Boss AND every
# delegated run, so these caps bound the whole ticket, not each agent separately.
MAX_DEPTH = 3  # Boss -> specialist -> specialist -> specialist at most
TICKET_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60, total_tokens_limit=250_000)
MODEL_SETTINGS = {"max_tokens": 4000, "parallel_tool_calls": False}

AGENT_NAMES: tuple[str, ...] = get_args(AgentName)

# Least privilege: which MCP tools each agent may call. Only Accounting touches money.
TOOL_ACCESS: dict[str, set[str]] = {
    "boss": {"get_shop_today", "list_open_tickets", "get_ticket", "update_ticket",
             "get_approval_status", "get_cash_and_obligations"},
    "inventory": {"get_shop_today", "get_ticket", "check_stock_and_price", "list_vendors",
                  "check_vendor_status", "draft_purchase_order"},
    "accounting": {"get_shop_today", "get_ticket", "get_cash_and_obligations", "check_stock_and_price",
                   "check_vendor_status", "list_payments", "request_payment_approval",
                   "get_approval_status", "pay_bill"},
    "facilities": {"get_shop_today", "get_ticket", "get_lease", "get_cash_and_obligations",
                   "get_approval_status"},
    "customer_service": {"get_shop_today", "get_ticket", "check_stock_and_price", "draft_customer_message"},
}

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

for _folder in (HW_DIR, *HW_DIR.parents):
    if load_dotenv(_folder / ".env"):
        break


def build_mcp_toolset() -> MCPToolset:
    """One stdio connection to the campus-customs MCP server, shared by the whole team."""
    return MCPToolset(PythonStdioTransport(SERVER_PATH, python_cmd=sys.executable, cwd=str(HW_DIR)))


def _build_model() -> OpenAIChatModel:
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing from the environment (.env).")
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(api_key=key, base_url=PORTKEY_BASE_URL))


def _allowed(agent_name: str, ctx: RunContext[TeamDeps], tool_def) -> bool:
    return tool_def.name in TOOL_ACCESS[agent_name]


class CampusCustomsTeam:
    """Builds the five agents and runs them with a fully audited agent loop."""

    def __init__(self, toolset: MCPToolset):
        model = _build_model()
        self.agents: dict[str, Agent] = {}
        for name in AGENT_NAMES:
            self.agents[name] = Agent(
                model,
                name=name,
                deps_type=TeamDeps,
                output_type=TicketDecision if name == "boss" else AgentReport,
                instructions=(PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"),
                toolsets=[toolset.filtered(partial(_allowed, name))],
                tools=[self._delegate_tool()],
                model_settings=MODEL_SETTINGS,
                retries=2,
            )

    def _delegate_tool(self):
        team = self

        async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict:
            """Hand a specific, self-contained task to a teammate and get their report back.

            to_agent: boss, inventory, accounting, facilities, or customer_service.
            task: exactly what you need, including ticket id, SKU/size/qty, invoice id, or lease id.
            """
            parent = ctx.deps
            refused = None
            if to_agent == parent.agent:
                refused = "You can't delegate to yourself."
            elif to_agent in parent.chain:
                refused = f"{to_agent} is already waiting on you in this chain; answer with what you have."
            elif parent.depth + 1 > MAX_DEPTH:
                refused = f"Delegation depth limit ({MAX_DEPTH}) reached; answer with what you have."
            if refused:
                log_event(parent, 0, "delegation_refused", {"to_agent": to_agent, "task": task, "reason": refused})
                return {"delegated": False, "error": refused}

            log_event(parent, 0, "delegation", {"to_agent": to_agent, "task": task})
            child = TeamDeps(run_id=parent.run_id, ticket_id=parent.ticket_id, agent=to_agent,
                             chain=[*parent.chain, parent.agent])
            try:
                report = await team.run_agent(to_agent, task, child, usage=ctx.usage)
            except UsageLimitExceeded:
                raise  # the whole ticket is over budget: stop everything
            except Exception as exc:  # report teammate failures back instead of crashing the caller
                return {"delegated": True, "error": f"{to_agent} failed: {type(exc).__name__}: {exc}"}
            return {"delegated": True, "report": report.model_dump()}

        return delegate

    async def run_agent(self, name: str, task: str, deps: TeamDeps, usage: RunUsage | None = None):
        """The agent loop: model -> tool calls -> tool results -> ... -> structured output.

        Each step is appended to the audit trail as it happens.
        """
        agent = self.agents[name]
        step = 0

        def log(event: str, detail: dict, tokens: dict | None = None) -> None:
            nonlocal step
            step += 1
            log_event(deps, step, event, detail, tokens)

        log("run_start", {"task": task, "model": MODEL_NAME, "allowed_mcp_tools": sorted(TOOL_ACCESS[name])})
        try:
            async with agent.iter(task, deps=deps, usage=usage, usage_limits=TICKET_LIMITS) as run:
                async for node in run:
                    if Agent.is_call_tools_node(node):
                        resp = node.model_response
                        calls = [p for p in resp.parts if isinstance(p, ToolCallPart)]
                        text = " ".join(p.content for p in resp.parts if isinstance(p, TextPart)).strip()
                        log("model_response",
                            {"text": text, "tool_calls": [c.tool_name for c in calls],
                             "finish_reason": resp.finish_reason},
                            {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens})
                        for c in calls:
                            log("tool_call", {"tool": c.tool_name, "tool_call_id": c.tool_call_id, "args": c.args})
                    elif Agent.is_model_request_node(node):
                        for p in node.request.parts:
                            if isinstance(p, ToolReturnPart):
                                log("tool_result", {"tool": p.tool_name, "tool_call_id": p.tool_call_id,
                                                    "output": p.content})
                            elif isinstance(p, RetryPromptPart):
                                log("retry", {"tool": p.tool_name, "content": p.model_response()})
            output = run.result.output
            total = run.usage
            log("run_end", {"output": output.model_dump()},
                {"ticket_total_input": total.input_tokens, "ticket_total_output": total.output_tokens,
                 "ticket_total_requests": total.requests, "ticket_total_tool_calls": total.tool_calls})
            return output
        except Exception as exc:
            log("run_error", {"error_type": type(exc).__name__, "error": str(exc)})
            raise

    async def run_ticket(self, ticket_id: int, run_id: str) -> TicketDecision:
        """The Boss works one ticket end to end, delegating as needed."""
        deps = TeamDeps(run_id=run_id, ticket_id=ticket_id, agent="boss")
        task = (f"Work ticket {ticket_id}. Read it, delegate to the right teammates, make the final call, "
                f"update the ticket, and return your TicketDecision.")
        return await self.run_agent("boss", task, deps, usage=RunUsage())
