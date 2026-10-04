"""FastAPI backend for the Campus Customs agent dashboard.

Start from the backend/ folder:
    uvicorn main:app --reload --port 8000

Shop facts (tickets, cash) come through the campus-customs MCP server, the same hub
the agents use. Payments still need a human: the approve route records the human's
decision first, and only then calls the MCP pay_bill tool.
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import approvals
from agents import CampusCustomsTeam, build_mcp_toolset
from audit import AUDIT_PATH
from team import reset_database

state: dict = {}
run_lock = asyncio.Lock()  # one team run at a time so tickets don't trip over each other


@asynccontextmanager
async def lifespan(app: FastAPI):
    toolset = build_mcp_toolset()
    async with toolset:
        state["toolset"] = toolset
        state["team"] = CampusCustomsTeam(toolset)
        yield
    state.clear()


app = FastAPI(title="Campus Customs Agent Desk", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp(tool: str, args: dict | None = None):
    return await state["toolset"].direct_call_tool(tool, args or {})


class HumanDecision(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the human clicking approve or deny.")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/tickets")
async def get_tickets():
    """All tickets with status and whether each is open or resolved."""
    result = await mcp("list_tickets")
    return [{**t, "state": "open" if t["is_open"] else "resolved"} for t in result["tickets"]]


@app.post("/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int):
    """Run the agent team (Boss first) on one ticket and return the Boss's decision."""
    ticket = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not ticket["found"]:
        raise HTTPException(404, ticket["error"])
    if run_lock.locked():
        raise HTTPException(409, "The team is already working a ticket. Try again when it finishes.")
    async with run_lock:
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        try:
            decision = await state["team"].run_ticket(ticket_id, run_id)
        except Exception as exc:
            raise HTTPException(500, f"Team run failed: {type(exc).__name__}: {exc}")
    return {"run_id": run_id, "decision": decision.model_dump()}


class ResolveRequest(BaseModel):
    resolved_by: str = Field(min_length=1)
    note: str = ""


@app.post("/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: int, body: ResolveRequest):
    """A human marks a ticket resolved after the run (through MCP update_ticket)."""
    note = f"Marked resolved by {body.resolved_by.strip()} from the dashboard. {body.note}".strip()
    result = await mcp("update_ticket", {"ticket_id": ticket_id, "status": "resolved", "note": note})
    if not result["updated"]:
        raise HTTPException(400, result["error"])
    return result


@app.get("/drafts")
async def get_drafts():
    """Local customer message and purchase order drafts (never sent)."""
    if not approvals.DRAFTS_PATH.exists() or not approvals.DRAFTS_PATH.read_text(encoding="utf-8").strip():
        return []
    return json.loads(approvals.DRAFTS_PATH.read_text(encoding="utf-8"))


@app.get("/events")
async def get_events(limit: int = Query(50, ge=1, le=500), ticket_id: int | None = None,
                     run_id: str | None = None):
    """Most recent agent-loop events from output/audit_trail.json, oldest first."""
    if not AUDIT_PATH.exists() or not AUDIT_PATH.read_text(encoding="utf-8").strip():
        return {"total": 0, "events": []}
    events = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if ticket_id is not None:
        events = [e for e in events if e["ticket_id"] == ticket_id]
    if run_id is not None:
        events = [e for e in events if e["run_id"] == run_id]
    return {"total": len(events), "events": events[-limit:]}


@app.get("/approvals")
async def get_approvals():
    """Payment approval requests and purchase order drafts waiting on a human."""
    drafts = []
    if approvals.DRAFTS_PATH.exists() and approvals.DRAFTS_PATH.read_text(encoding="utf-8").strip():
        drafts = json.loads(approvals.DRAFTS_PATH.read_text(encoding="utf-8"))
    return {"payments": approvals.load(), "purchase_orders": [d for d in drafts if d["kind"] == "purchase_order"]}


@app.post("/approvals/{item_id}/approve")
async def approve(item_id: str, body: HumanDecision):
    """A human approves a payment (APR-...) or purchase order draft (PO-...).

    Payments: the human approval is recorded, then the MCP pay_bill tool pays it,
    which still refuses if cash can't cover it. Purchase orders: marked approved,
    never sent to a vendor.
    """
    try:
        if item_id.startswith("APR-"):
            record = approvals.decide(item_id, True, body.approved_by)
            payment = await mcp("pay_bill", {"approval_id": item_id})
            return {"approval": record, "payment": payment}
        if item_id.startswith("PO-"):
            return {"purchase_order": approvals.decide_purchase_order(item_id, True, body.approved_by)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    raise HTTPException(400, "Id must start with APR- (payment) or PO- (purchase order).")


@app.post("/approvals/{item_id}/deny")
async def deny(item_id: str, body: HumanDecision):
    """A human denies a payment request or rejects a purchase order draft."""
    try:
        if item_id.startswith("APR-"):
            return {"approval": approvals.decide(item_id, False, body.approved_by)}
        if item_id.startswith("PO-"):
            return {"purchase_order": approvals.decide_purchase_order(item_id, False, body.approved_by)}
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    raise HTTPException(400, "Id must start with APR- (payment) or PO- (purchase order).")


@app.get("/cash")
async def get_cash():
    """Current checking balance from cash_accounts."""
    result = await mcp("get_cash_and_obligations")
    checking = next((a for a in result["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {"account": "checking", "balance": checking["balance"], "as_of": checking["date"]}


@app.post("/reset")
async def reset():
    """Restore data/campus_customs_new.db from the original and clear drafts and approvals.
    The audit trail is kept."""
    if run_lock.locked():
        raise HTTPException(409, "Can't reset while the team is running.")
    reset_database()
    return {"reset": True, "message": "Working database restored from data/campus_customs.db."}
