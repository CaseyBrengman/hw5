"""Campus Customs MCP server.

The single hub for shop facts and shop actions used by the agent team (Boss,
Inventory, Accounting, Facilities, Customer Service). Reads and writes ONLY
data/campus_customs_new.db; the original data/campus_customs.db is never touched.

Every value returned comes straight from the database. If something is not in
the database, the tool says so instead of guessing.

Local-only files (nothing is ever sent outside this project):
  output/drafts.json     customer messages and purchase orders, drafts only
  output/approvals.json  payment approval requests; only a human can approve
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from fastmcp import FastMCP

HW_DIR = Path(__file__).resolve().parent.parent
DB_PATH = HW_DIR / "data" / "campus_customs_new.db"
DRAFTS_PATH = HW_DIR / "output" / "drafts.json"
APPROVALS_PATH = HW_DIR / "output" / "approvals.json"

TICKET_STATUSES = ("open", "in_progress", "waiting_approval", "waiting_vendor", "resolved", "escalated")

mcp = FastMCP("campus-customs")


# ---------- helpers ----------

@contextmanager
def _connect():
    """Open the working DB, commit on success (roll back on error), and always close
    the file handle so resets and file moves are never blocked."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' is desk.date_today, not the real calendar date."""
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()["date_today"])


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _load_json(path: Path) -> list:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else []


def _save_json(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _open_invoices(conn: sqlite3.Connection, today: date, vendor_id: int | None = None) -> list[dict]:
    sql = "SELECT id, vendor_id, amount, due_date, description FROM invoices WHERE status = 'open'"
    args: tuple = ()
    if vendor_id is not None:
        sql += " AND vendor_id = ?"
        args = (vendor_id,)
    out = []
    for inv in _rows(conn.execute(sql + " ORDER BY due_date", args)):
        days_past_due = (today - date.fromisoformat(inv["due_date"])).days
        inv["overdue"] = days_past_due > 0
        inv["days_past_due"] = max(days_past_due, 0)
        out.append(inv)
    return out


def _add_one_month(d: date) -> date:
    month = d.month % 12 + 1
    year = d.year + (d.month == 12)
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue


# ---------- desk and tickets ----------

def get_shop_today() -> dict:
    """Return the shop's 'today' (desk.date_today) and desk notes.

    Always use this date, never the real calendar date, for overdue checks,
    days-until-due, and vendor arrival dates.
    """
    with _connect() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk").fetchone()
    return {"date_today": row["date_today"], "notes": row["notes"]}


def list_open_tickets() -> dict:
    """List every ticket that is not resolved, oldest first, with all link fields
    (sku, size, qty, lease_id, invoice_id) so the Boss can route each one."""
    with _connect() as conn:
        tickets = _rows(conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at"
        ))
    return {"count": len(tickets), "tickets": tickets}


def list_tickets() -> dict:
    """List every ticket (any status) with is_open = status is not 'resolved'."""
    with _connect() as conn:
        tickets = _rows(conn.execute("SELECT * FROM tickets ORDER BY id"))
    for t in tickets:
        t["is_open"] = t["status"] != "resolved"
    return {"count": len(tickets), "tickets": tickets}


def get_ticket(ticket_id: int) -> dict:
    """Return one ticket with all of its fields."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return {"found": False, "error": f"No ticket with id={ticket_id}."}
    return {"found": True, **dict(row)}


def update_ticket(ticket_id: int, status: str, note: str) -> dict:
    """Set a ticket's status and append a dated note to tickets.notes.

    status must be one of: open, in_progress, waiting_approval, waiting_vendor,
    resolved, escalated. The note is appended; earlier notes are kept.
    """
    status = status.strip().lower()
    if status not in TICKET_STATUSES:
        return {"updated": False, "error": f"status must be one of {list(TICKET_STATUSES)}."}
    if not note or not note.strip():
        return {"updated": False, "error": "A note explaining the update is required."}
    with _connect() as conn:
        row = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"updated": False, "error": f"No ticket with id={ticket_id}."}
        stamped = f"[{_today(conn).isoformat()}] {note.strip()}"
        notes = f"{row['notes']}\n{stamped}" if row["notes"] else stamped
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
    return {"updated": True, "ticket_id": ticket_id, "status": status, "notes": notes}


# ---------- inventory and vendors ----------

def check_stock_and_price(sku: str, size: str, qty_requested: int) -> dict:
    """Check whether a SKU/size can fill an order and what it costs.

    Returns on-hand qty, shortfall, shelf location, unit cost, list price,
    the list-price total for the request, and the per-unit margin. Use it for
    customer orders and price-override (discount) requests.
    """
    with _connect() as conn:
        item = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if item is None:
            return {"found": False, "error": f"No inventory row for sku={sku} size={size}."}
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()

    on_hand = item["qty"]
    result = {
        "found": True,
        "sku": item["sku"],
        "name": item["name"],
        "size": item["size"],
        "location": item["location"],
        "qty_on_hand": on_hand,
        "qty_requested": qty_requested,
        "can_fill_from_stock": on_hand >= qty_requested,
        "shortfall": max(qty_requested - on_hand, 0),
    }
    if price is None:
        result["pricing"] = "No pricing row for this SKU."
    else:
        result.update(
            unit_cost=price["unit_cost"],
            list_price=price["list_price"],
            margin_per_unit=round(price["list_price"] - price["unit_cost"], 2),
            list_total_for_request=round(price["list_price"] * qty_requested, 2),
            floor_price_per_unit=price["unit_cost"],  # never sell below cost
        )
    return result


def list_vendors(sku: str = "") -> dict:
    """List every vendor with specialty, lead_days, and whether it can ship now.

    If a sku is given, also returns that item's product name (from inventory)
    and any past or open invoices whose description mentions the sku, which is
    the only restock history the database has. The database has no direct
    sku-to-vendor table: match on specialty and invoice history, and say so.
    """
    with _connect() as conn:
        today = _today(conn)
        vendors = _rows(conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"))
        for v in vendors:
            open_inv = _open_invoices(conn, today, v["id"])
            v["open_invoice_ids"] = [i["id"] for i in open_inv]
            v["can_ship"] = not open_inv
        result: dict = {"shop_today": today.isoformat(), "vendors": vendors}
        if sku:
            names = [r["name"] for r in conn.execute("SELECT DISTINCT name FROM inventory WHERE sku = ?", (sku,))]
            history = _rows(conn.execute(
                "SELECT id, vendor_id, amount, due_date, status, description FROM invoices "
                "WHERE description LIKE ? ORDER BY due_date",
                (f"%{sku}%",),
            ))
            result["sku"] = sku
            result["product_name"] = names[0] if names else None
            result["invoice_history_for_sku"] = history
            result["note"] = "No sku-to-vendor table exists; use specialty and invoice history to choose."
    return result


def check_vendor_status(vendor_id: int) -> dict:
    """Check whether a vendor can ship right now and when an order would arrive.

    A vendor will not ship while it has any unpaid open invoice. Lists those
    invoices (flagging overdue ones against desk.date_today) and, if the vendor
    can ship, the expected arrival date = today + vendors.lead_days.
    """
    with _connect() as conn:
        today = _today(conn)
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        if vendor is None:
            return {"found": False, "error": f"No vendor with id={vendor_id}."}
        invoices = _open_invoices(conn, today, vendor_id)

    can_ship = not invoices
    return {
        "found": True,
        "vendor_id": vendor["id"],
        "name": vendor["name"],
        "specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "shop_today": today.isoformat(),
        "can_ship": can_ship,
        "blocked_reason": None if can_ship else "Vendor has unpaid open invoice(s); pay them before ordering.",
        "open_invoices": invoices,
        "amount_owed": round(sum(i["amount"] for i in invoices), 2),
        "arrival_if_ordered_today": (today + timedelta(days=vendor["lead_days"])).isoformat() if can_ship else None,
    }


def draft_purchase_order(vendor_id: int, sku: str, size: str, qty: int, ticket_id: int, drafted_by: str) -> dict:
    """Save a purchase order DRAFT to output/drafts.json. Nothing is sent to the vendor.

    Refuses if the vendor still has an unpaid open invoice (it will not ship).
    Cost uses pricing.unit_cost and arrival uses today + vendors.lead_days.
    A human must review the draft before anything is ordered.
    """
    if qty <= 0:
        return {"saved": False, "error": "qty must be positive."}
    status = check_vendor_status(vendor_id)
    if not status["found"]:
        return {"saved": False, "error": status["error"]}
    if not status["can_ship"]:
        return {"saved": False, "error": "Refused: vendor has unpaid open invoice(s) and will not ship.",
                "open_invoices": status["open_invoices"]}
    with _connect() as conn:
        item = conn.execute("SELECT name FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
    if item is None or price is None:
        return {"saved": False, "error": f"No inventory/pricing row for sku={sku} size={size}."}

    drafts = _load_json(DRAFTS_PATH)
    draft = {
        "draft_id": f"PO-{len(drafts) + 1:03d}",
        "kind": "purchase_order",
        "status": "draft - needs human review, NOT sent",
        "ticket_id": ticket_id,
        "vendor_id": vendor_id,
        "vendor_name": status["name"],
        "sku": sku,
        "product_name": item["name"],
        "size": size,
        "qty": qty,
        "unit_cost": price["unit_cost"],
        "total_cost": round(price["unit_cost"] * qty, 2),
        "expected_arrival": status["arrival_if_ordered_today"],
        "drafted_by": drafted_by,
        "created_at": _now(),
    }
    drafts.append(draft)
    _save_json(DRAFTS_PATH, drafts)
    return {"saved": True, **draft}


# ---------- money ----------

def get_cash_and_obligations() -> dict:
    """Return cash balances, every open invoice (overdue flagged), and every lease's
    next rent, with totals and the cash left if everything owed were paid.

    Read-only. Use it before recommending any payment so cash never goes negative.
    """
    with _connect() as conn:
        today = _today(conn)
        accounts = _rows(conn.execute("SELECT name, balance, date FROM cash_accounts"))
        invoices = _open_invoices(conn, today)
        leases = _rows(conn.execute("SELECT id, space_name, landlord, monthly_rent, next_due FROM leases"))
    for lease in leases:
        lease["days_until_due"] = (date.fromisoformat(lease["next_due"]) - today).days
    total_cash = round(sum(a["balance"] for a in accounts), 2)
    owed = round(sum(i["amount"] for i in invoices) + sum(l["monthly_rent"] for l in leases), 2)
    return {
        "shop_today": today.isoformat(),
        "cash_accounts": accounts,
        "total_cash": total_cash,
        "open_invoices": invoices,
        "rent_due": leases,
        "total_owed": owed,
        "cash_after_paying_all": round(total_cash - owed, 2),
    }


def get_lease(lease_id: int) -> dict:
    """Return one lease with rent, landlord, next_due, and days until due
    (negative means overdue) measured from desk.date_today."""
    with _connect() as conn:
        today = _today(conn)
        row = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
    if row is None:
        return {"found": False, "error": f"No lease with id={lease_id}."}
    lease = dict(row)
    days = (date.fromisoformat(lease["next_due"]) - today).days
    return {"found": True, **lease, "shop_today": today.isoformat(), "days_until_due": days, "overdue": days < 0}


def list_payments() -> dict:
    """Return every recorded payment (the audit log of money that has left the shop)."""
    with _connect() as conn:
        payments = _rows(conn.execute("SELECT * FROM payments ORDER BY id"))
    return {"count": len(payments), "payments": payments}


def request_payment_approval(kind: str, ref_id: int, ticket_id: int, requested_by: str, reason: str) -> dict:
    """Ask an external human to approve paying an invoice or rent. Does NOT pay.

    kind: 'invoice' or 'rent'. ref_id: invoices.id or leases.id. The amount is
    read from the database. Saves a 'pending' request to output/approvals.json;
    only a human can mark it approved. Refuses requests cash cannot cover.
    """
    kind = kind.strip().lower()
    if kind not in ("invoice", "rent"):
        return {"requested": False, "error": "kind must be 'invoice' or 'rent'."}
    with _connect() as conn:
        if kind == "invoice":
            bill = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if bill is None:
                return {"requested": False, "error": f"No invoice with id={ref_id}."}
            if bill["status"] != "open":
                return {"requested": False, "error": f"Invoice {ref_id} is '{bill['status']}', not open."}
            amount = bill["amount"]
        else:
            bill = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if bill is None:
                return {"requested": False, "error": f"No lease with id={ref_id}."}
            amount = bill["monthly_rent"]
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()["balance"]

    approvals = _load_json(APPROVALS_PATH)
    for a in approvals:
        if a["kind"] == kind and a["ref_id"] == ref_id and a["status"] in ("pending", "approved"):
            return {"requested": False, "error": "An approval for this bill already exists.", "existing": a}
    committed = sum(a["amount"] for a in approvals if a["status"] in ("pending", "approved"))
    if amount + committed > cash:
        return {"requested": False, "error": "Refused: cash cannot cover this plus already-requested payments.",
                "amount": amount, "already_requested": committed, "cash": cash}

    req = {
        "approval_id": f"APR-{len(approvals) + 1:03d}",
        "kind": kind,
        "ref_id": ref_id,
        "ticket_id": ticket_id,
        "amount": amount,
        "reason": reason,
        "requested_by": requested_by,
        "requested_at": _now(),
        "status": "pending",
        "decided_by": None,
        "decided_at": None,
    }
    approvals.append(req)
    _save_json(APPROVALS_PATH, approvals)
    return {"requested": True, **req, "next_step": "Wait for a human to approve. Do not call pay_bill until status is 'approved'."}


def get_approval_status(approval_id: str) -> dict:
    """Check whether a human has approved, denied, or not yet decided a payment request."""
    for a in _load_json(APPROVALS_PATH):
        if a["approval_id"] == approval_id:
            return {"found": True, **a}
    return {"found": False, "error": f"No approval with id={approval_id}."}


def pay_bill(approval_id: str, account: str = "checking") -> dict:
    """Pay an invoice or rent ONLY if a human has approved this approval_id.

    The amount always comes from the database, never the caller. Refuses if the
    request is not 'approved' by a human, if the bill changed, or if the account
    can't cover it, so cash never goes negative and never comes in.

    On success, in one transaction: inserts a payments row (approved_by = the
    human), lowers cash_accounts.balance, and marks the invoice 'paid' or moves
    the lease's next_due forward one month. The approval is marked 'paid'.
    """
    approvals = _load_json(APPROVALS_PATH)
    req = next((a for a in approvals if a["approval_id"] == approval_id), None)
    if req is None:
        return {"paid": False, "error": f"No approval with id={approval_id}. Request human approval first."}
    if req["status"] != "approved" or not req.get("decided_by"):
        return {"paid": False, "error": f"Refused: approval {approval_id} is '{req['status']}', not approved by a human."}
    kind, ref_id = req["kind"], req["ref_id"]

    with _connect() as conn:
        today = _today(conn)
        if kind == "invoice":
            bill = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if bill is None or bill["status"] != "open":
                return {"paid": False, "error": f"Invoice {ref_id} is missing or not open."}
            amount = bill["amount"]
        else:
            bill = conn.execute("SELECT monthly_rent, next_due FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if bill is None:
                return {"paid": False, "error": f"No lease with id={ref_id}."}
            amount = bill["monthly_rent"]
        if amount != req["amount"]:
            return {"paid": False, "error": "Refused: bill amount changed since approval. Request a new approval."}

        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            return {"paid": False, "error": f"No cash account named '{account}'."}
        if amount <= 0:
            return {"paid": False, "error": "Refused: amount must be positive (cash only goes out)."}
        if acct["balance"] < amount:
            return {"paid": False, "error": "Refused: insufficient cash.", "amount": amount,
                    "balance": acct["balance"], "short_by": round(amount - acct["balance"], 2)}

        new_balance = round(acct["balance"] - amount, 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                     (new_balance, today.isoformat(), account))
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, account, today.isoformat(), req["decided_by"]),
        )
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            updated = {"invoice_status": "paid"}
        else:
            next_due = _add_one_month(date.fromisoformat(bill["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, ref_id))
            updated = {"lease_next_due": next_due}

    req["status"] = "paid"
    req["payment_id"] = cur.lastrowid
    _save_json(APPROVALS_PATH, approvals)
    return {"paid": True, "payment_id": cur.lastrowid, "approval_id": approval_id, "kind": kind, "ref_id": ref_id,
            "amount": amount, "account": account, "new_balance": new_balance, "paid_at": today.isoformat(),
            "approved_by": req["decided_by"], **updated}


# ---------- customer messages ----------

def draft_customer_message(ticket_id: int, to: str, subject: str, body: str, drafted_by: str) -> dict:
    """Save a customer message DRAFT to output/drafts.json. It is NEVER emailed or sent.

    `to` must be the ticket's requester (from the tickets table).
    """
    ticket = get_ticket(ticket_id)
    if not ticket["found"]:
        return {"saved": False, "error": ticket["error"]}
    if to.strip().lower() != ticket["requester"].strip().lower():
        return {"saved": False, "error": f"'to' must be the ticket requester: {ticket['requester']}."}
    drafts = _load_json(DRAFTS_PATH)
    draft = {
        "draft_id": f"MSG-{len(drafts) + 1:03d}",
        "kind": "customer_message",
        "status": "draft - NOT sent",
        "ticket_id": ticket_id,
        "to": ticket["requester"],
        "subject": subject,
        "body": body,
        "drafted_by": drafted_by,
        "created_at": _now(),
    }
    drafts.append(draft)
    _save_json(DRAFTS_PATH, drafts)
    return {"saved": True, **draft}


for _tool in (
    get_shop_today, list_tickets, list_open_tickets, get_ticket, update_ticket,
    check_stock_and_price, list_vendors, check_vendor_status, draft_purchase_order,
    get_cash_and_obligations, get_lease, list_payments,
    request_payment_approval, get_approval_status, pay_bill,
    draft_customer_message,
):
    mcp.tool(_tool)


if __name__ == "__main__":
    mcp.run(show_banner=False)
