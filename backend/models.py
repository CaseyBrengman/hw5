"""Data types shared by the Campus Customs agent team."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["open", "in_progress", "waiting_approval", "waiting_vendor", "resolved", "escalated"]


@dataclass
class TeamDeps:
    """Passed to every agent run. Tracks who is working and how deep the delegation chain is."""

    run_id: str
    ticket_id: int | None
    agent: AgentName
    chain: list[AgentName] = field(default_factory=list)  # agents above this one, Boss first

    @property
    def depth(self) -> int:
        return len(self.chain)


class AgentReport(BaseModel):
    """What a specialist agent (Inventory, Accounting, Facilities, Customer Service) hands back."""

    agent: AgentName
    summary: str = Field(description="Plain-language answer to the task, 2-5 sentences.")
    facts_used: list[str] = Field(
        default_factory=list,
        description="Each fact with its source tool, e.g. 'CC-HOOD-NAVY M qty_on_hand=8 (check_stock_and_price)'.",
    )
    actions_taken: list[str] = Field(
        default_factory=list, description="Anything written: drafts saved, approvals requested, payments made."
    )
    needs_human: list[str] = Field(
        default_factory=list, description="Decisions or approvals only a human can make."
    )
    blocked_by: str | None = Field(default=None, description="What is stopping progress, if anything.")


class TicketDecision(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int
    assigned_agents: list[AgentName] = Field(description="Agents the Boss delegated to, in order.")
    decision: str = Field(description="The Boss's final call and the reason, 2-6 sentences.")
    final_status: TicketStatus
    actions_taken: list[str] = Field(default_factory=list)
    drafts_created: list[str] = Field(default_factory=list, description="draft_id values from output/drafts.json.")
    approvals_requested: list[str] = Field(
        default_factory=list, description="approval_id values waiting on a human."
    )
    needs_human: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    """One row in output/audit_trail.json."""

    timestamp: str
    run_id: str
    ticket_id: int | None
    agent: AgentName
    depth: int
    chain: list[str]
    step: int
    event: Literal[
        "run_start", "model_response", "tool_call", "tool_result", "retry", "delegation",
        "delegation_refused", "run_end", "run_error",
    ]
    detail: dict
    tokens: dict | None = None
