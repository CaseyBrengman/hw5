# Campus Customs MCP Server

A FastMCP server and the single hub for shop facts and shop actions for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). The tools only return data that is actually in the database and never make values up.

## Database and local files

- `data/campus_customs_new.db`: the working copy. This is the **only** database the server reads and writes.
- `data/campus_customs.db`: the original. The server never opens it. It is used only to reset the working copy before a full run.
- `output/drafts.json`: customer message and purchase order **drafts**. Nothing is ever sent.
- `output/approvals.json`: payment approval requests. Only a human can approve them (`backend/approvals.py`).

## Tools

| Tool | What it does |
|---|---|
| `get_shop_today()` | The shop's "today" (`desk.date_today`), used for every overdue or due-date check. |
| `list_open_tickets()` | Every ticket that isn't resolved, with its sku/size/qty/lease/invoice links. |
| `get_ticket(ticket_id)` | One ticket with all its fields. |
| `update_ticket(ticket_id, status, note)` | Sets the status and appends a dated note. |
| `check_stock_and_price(sku, size, qty_requested)` | On-hand qty, shortfall, location, unit cost, list price, margin, and list total. |
| `list_vendors(sku="")` | All vendors with specialty, lead days, and whether they can ship, plus any invoice history for a SKU. |
| `check_vendor_status(vendor_id)` | The vendor's open invoices (overdue flagged), whether it can ship, and the arrival date (today + lead_days). |
| `draft_purchase_order(vendor_id, sku, size, qty, ticket_id, drafted_by)` | Saves a PO draft. Refuses if the vendor has an unpaid open invoice. |
| `get_cash_and_obligations()` | Cash balances, open invoices, upcoming rent, totals, and the cash left after paying everything. |
| `get_lease(lease_id)` | Rent, landlord, next due date, and days until due. |
| `list_payments()` | Every recorded payment. |
| `request_payment_approval(kind, ref_id, ticket_id, requested_by, reason)` | Creates a *pending* approval request for an invoice or rent. Doesn't pay. Refuses if cash can't cover it. |
| `get_approval_status(approval_id)` | Pending, approved, denied, or paid. |
| `pay_bill(approval_id, account="checking")` | Pays **only** if a human approved the request. The amount comes from the DB, and it refuses if cash is short. On success it logs the payment, lowers cash, and marks the invoice paid or moves the rent due date forward. |
| `draft_customer_message(ticket_id, to, subject, body, drafted_by)` | Saves a message draft addressed to the ticket's requester. Never sent. |

## Run

```bash
pip install -r requirements.txt
python mcp_server/server.py
```
