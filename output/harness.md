# Harness  -  Campus Customs

# Problem 2  -  Study the Campus Customs Database

Source: `data/campus_customs.db` (original, read-only). All agent and MCP writes go to `data/campus_customs_new.db`.

Agents: Boss, Inventory, Accounting, Facilities, Customer Service.

## Table Notes

### desk

**Fields:** `date_today`, `notes`

**Why it matters:** This is the shop's clock. `date_today` (2026-08-31) is what "today" means for every agent, so it is how we decide whether an invoice is overdue, how soon rent is due, and when a vendor shipment would arrive (today + lead time). Every agent should read it before making a time-based decision instead of using the real calendar date.

### inventory

**Fields:** `sku`, `name`, `size`, `qty`, `location` (primary key: `sku` + `size`)

**Why it matters:** This is the Inventory agent's main table. It tells us whether a customer order can be filled from stock right away (white tee size S has 0, navy hoodie size M has 8). The Customer Service agent relies on it to give customers honest answers, and the Boss uses it to decide whether a ticket needs a restock.

### pricing

**Fields:** `sku`, `unit_cost`, `list_price`

**Why it matters:** This gives the cost and the selling price for each SKU, which together set the margin. The Accounting agent uses `unit_cost` to price restocks, and the Boss and Accounting use the margin to decide how much discount the shop can afford (for example, the bulk hoodie request: $22 cost against a $58 list price). Customer Service quotes from `list_price`.

### vendors

**Fields:** `id`, `name`, `specialty`, `lead_days`

**Why it matters:** This is where lead times come from. The Inventory agent uses `specialty` to pick the right supplier and `lead_days` to give an arrival date. Vendors connect to `invoices`, and a vendor won't ship while it has an unpaid open invoice, so this table plus `invoices` tells Inventory whether a restock is actually possible.

### leases

**Fields:** `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`

**Why it matters:** This is the Facilities agent's table. It holds the rent amount and its due date (2026-09-02), which Facilities compares against `desk.date_today`. Rent is a large cash outflow ($2,400), so Facilities has to work with Accounting and get human approval before anything is paid.

### cash_accounts

**Fields:** `name`, `balance`, `date`

**Why it matters:** This is the shop's only source of truth for available money ($3,400 in checking). The pay tool must check it and refuse any payment that would push the balance below zero. Cash only goes down in this activity because we are not modeling revenue. It belongs to the Accounting agent, and the Boss checks it when deciding which bills to pay first.

### payments

**Fields:** `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`

**Why it matters:** This is the audit log of money that has left the shop (empty to start). A row should be written only after an external human approves a payment, and `approved_by` records who approved it. `kind` + `ref_id` point back to what was paid (an invoice or a lease). Each payment must also update the related tables: `cash_accounts.balance`, `invoices.status`, or `leases.next_due`.

### invoices

**Fields:** `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`

**Why it matters:** These are bills owed to vendors. Accounting uses `due_date` against `desk.date_today` to flag overdue bills (invoice 501, $840, was due 2026-08-28, so it is overdue). An `open` invoice also blocks that vendor from shipping, so whether the shop can restock depends on whether the invoice is paid.

### tickets

**Fields:** `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`

**Why it matters:** This is the work queue that drives the whole team. The Boss reads open tickets and sends each one to the right agent based on `type`. The optional link fields (`sku`/`size`, `lease_id`, `invoice_id`) tell agents which other tables to look at. Agents close a ticket by updating `status` and `notes`.

## How the Open Tickets Link to the Tables

| Ticket | Type | Requester | Links | Agents involved |
|---|---|---|---|---|
| 101 | customer_order | Tauhid Zaman | `inventory`/`pricing` via CC-TEE-WHITE size S (qty 1); `invoices` via invoice 501 -> `vendors` id 1 (Bulldog Print Co, 5 lead days) | Customer Service, Inventory, Accounting, Boss |
| 102 | rent_notice | Elm City Properties | `leases` via lease 1 (Chapel Street shop, $2,400, due 2026-09-02) | Facilities, Accounting, Boss |
| 103 | price_override | Yale AI Club | `inventory`/`pricing` via CC-HOOD-NAVY size M (qty 20) | Customer Service, Inventory, Accounting, Boss |

**Ticket 101 (dependency chain):** The white tee in size S has 0 in stock, so it has to be reprinted. Bulldog Print Co does reprints, but invoice 501 ($840) is open and overdue, so Bulldog won't ship. To fill the order: human approves payment of invoice 501 -> invoice marked paid, payment logged, cash drops to $2,560 -> reorder from Bulldog -> arrives 5 days after the reorder date -> Customer Service drafts an update to the customer (draft only, never sent).

**Ticket 102 (cash timing):** Rent of $2,400 is due 2026-09-02, two days after today. Facilities asks Accounting to pay it with human approval. Paying both rent and invoice 501 comes to $3,240, which fits within the $3,400 balance and leaves $160. Any further payments would have to be refused.

**Ticket 103 (stock + margin):** The club wants 20 hoodies in size M, but only 8 are in stock, so 12 would need a restock (likely from Bulldog Print Co, which is also blocked by invoice 501). At list price the order is 20 x $58 = $1,160, with a unit cost of $22. Any discount has to keep the price above cost. Customer Service drafts the offer, and the Boss signs off on the override.

## Shop Rules the Harness Enforces

- `desk.date_today` is "today"; overdue = past due relative to it.
- Lead times come from `vendors.lead_days`.
- A vendor with an unpaid open invoice will not ship.
- Every payment needs external human approval first, and an approved payment must update `payments`, `cash_accounts`, and the related invoice or lease.
- The pay tool refuses any payment the cash balance can't cover. Cash never goes negative and never comes in.
- Reset `campus_customs_new.db` from the original before a full ticket-resolution run.
- Customer and vendor messages are local drafts only and are never sent.

# Problem 3  -  Build the MCP Server

Server: `mcp_server/server.py` (FastMCP, named `campus-customs`). It reads and writes only `data/campus_customs_new.db`.

### Tool 1: `check_stock_and_price(sku, size, qty_requested)`

- **Reads:** `inventory`, `pricing`
- **Helps resolve:** Ticket 101 (white tee, size S) and Ticket 103 (20 navy hoodies, size M, bulk discount)
- **Why it's best:** In one call it shows the 0-of-1 tee shortfall and the 8-of-20 hoodie shortfall, along with the $22 cost floor that any hoodie discount must stay above.

### Tool 2: `check_vendor_status(vendor_id)`

- **Reads:** `vendors`, `invoices`, `desk`
- **Helps resolve:** Ticket 101 (and the restock half of Ticket 103)
- **Why it's best:** It shows that Bulldog Print Co is blocked by invoice 501 ($840, 3 days overdue as of desk.date_today), so the agents know the tee can't be reprinted until that bill is paid and know the 5-day arrival date once it is.

### Tool 3: `pay_bill(kind, ref_id, approved_by, account="checking")`

- **Reads:** `invoices`, `leases`, `cash_accounts`, `desk`. **Writes:** `payments`, `cash_accounts`, `invoices` / `leases`
- **Helps resolve:** Ticket 102 (rent of $2,400 due 2026-09-02) and Ticket 101 (paying invoice 501 to unblock the vendor)
- **Why it's best:** It is the only way money leaves the shop: it refuses without a named human approver, refuses if cash can't cover the bill, takes the amount from the database instead of the agent, and updates every related table in one transaction.

# Problem 4  -  Add the MCP Server to Vibe Coder and Test Each Tool

- **Connection:** `.mcp.json` at the Homework 5 project root registers the `campus-customs` server (`python mcp_server/server.py`; during the homework it pointed at the local `.venv` Python with absolute paths, and for submission it uses relative paths so it works after cloning). Claude Code loaded it on restart and the three tools appeared as `mcp__campus-customs__*`.
- **Evidence:** `output/mcp_smoke.json` records the prompt, tool name, arguments, tool output, and a direct database check for each tool. All three match `data/campus_customs_new.db`.
- **pay_bill test:** This was a refusal test with no approver, so no money moved and the working database is still identical to the original.

# Problem 5  -  Build the Agent Team and Grow the MCP Tools

**Stack:** PydanticAI agents (`backend/agents.py`) on `gpt-5.6-luna` through Portkey (`PORTKEY_API_KEY` from `.env`). Every shop fact and action goes through the `campus-customs` MCP server over stdio; the backend has no direct database access for shop facts. Prompts live in `backend/prompts/` (one file per agent), data types in `backend/models.py`, the runner in `backend/team.py`, and the audit writer in `backend/audit.py`.

## The Agents

| Agent | Prompt | Job | MCP tools it may call | Output |
|---|---|---|---|---|
| Boss | `prompts/boss.md` | Reads each ticket, routes it, makes the final call (including approving or rejecting discounts), updates the ticket | get_shop_today, list_open_tickets, get_ticket, update_ticket, get_approval_status, get_cash_and_obligations | TicketDecision |
| Inventory | `prompts/inventory.md` | Stock by SKU and size, shortfalls, which vendor restocks the item, whether that vendor can ship, arrival dates, PO drafts | get_shop_today, get_ticket, check_stock_and_price, list_vendors, check_vendor_status, draft_purchase_order | AgentReport |
| Accounting | `prompts/accounting.md` | Cash, invoices, overdue bills, margins and discount floors, payment approval requests, paying after a human approves | get_shop_today, get_ticket, get_cash_and_obligations, check_stock_and_price, check_vendor_status, list_payments, request_payment_approval, get_approval_status, pay_bill | AgentReport |
| Facilities | `prompts/facilities.md` | Leases, rent, due dates, landlord notices | get_shop_today, get_ticket, get_lease, get_cash_and_obligations, get_approval_status | AgentReport |
| Customer Service | `prompts/customer_service.md` | Drafts honest customer and requester messages (never sent) | get_shop_today, get_ticket, check_stock_and_price, draft_customer_message | AgentReport |

**Full connectivity:** Every agent also has a `delegate(to_agent, task)` tool that can hand work to any of the other four and get back a structured report. To keep it from looping, an agent can't delegate to itself or to any agent already waiting on it in the current chain, and chains stop at 3 levels.

**Agent loop:** Each agent runs model -> tool calls -> tool results -> repeat, until it returns its structured output. `team.py` has the Boss work each open ticket; the Boss delegates as needed and closes the ticket with `update_ticket`.

## MCP Tools (15 total; 12 added in Problem 5)

| Tool | Tables / files used | Status |
|---|---|---|
| get_shop_today | desk | new |
| list_open_tickets | tickets | new |
| get_ticket | tickets | new |
| update_ticket | tickets (writes status + appends a dated note) | new |
| check_stock_and_price | inventory, pricing | from Problem 3 |
| list_vendors | vendors, invoices, inventory, desk | new |
| check_vendor_status | vendors, invoices, desk | from Problem 3 |
| draft_purchase_order | vendors, invoices, inventory, pricing, desk -> writes output/drafts.json | new |
| get_cash_and_obligations | cash_accounts, invoices, leases, desk | new |
| get_lease | leases, desk | new |
| list_payments | payments | new |
| request_payment_approval | invoices, leases, cash_accounts -> writes output/approvals.json (pending) | new |
| get_approval_status | output/approvals.json | new |
| pay_bill | output/approvals.json, invoices, leases, cash_accounts, payments, desk | **changed** |
| draft_customer_message | tickets -> writes output/drafts.json | new |

**pay_bill change:** In Problem 3, `pay_bill` took a typed-in `approved_by` name, which an agent could fake. It now takes only an `approval_id`, and it pays only if a human approved that request through `backend/approvals.py`, which is a human-only script and not an MCP tool. The `pay_bill` call recorded in `output/mcp_smoke.json` (Problem 4) used the old signature.

## Audit Trail

`output/audit_trail.json` is append-only and is never wiped, including by a database reset. Each agent-loop step adds one event with: timestamp, run_id, ticket_id, agent, depth, delegation chain, step number, event type (`run_start`, `model_response`, `tool_call`, `tool_result`, `retry`, `delegation`, `delegation_refused`, `run_end`, `run_error`), details (task, model text, tool name + arguments + call id, tool output, final output, or error), and token counts. Long outputs are truncated at 2,000 characters.

**Light test (ticket 102):** Boss -> Facilities (lease) -> Accounting (cash check + approval request APR-001, pending, no payment) -> Customer Service (draft MSG-002, not sent) -> Boss set the ticket to `waiting_approval`. That was 15 model requests and about 31k tokens. The database was reset afterward; the audit entries were kept.

## Safety

### Guardrails if agents had real customers and real money

1. **Human approval for every payment.** Agents can only *request* approval. Approval happens outside the agent system (`backend/approvals.py` for now, the dashboard later), and `pay_bill` checks for a recorded human decision.
2. **Amounts come from the system of record.** Agents never type in an amount. If a bill changes after approval, the payment is refused and needs a new approval.
3. **No overdraft and no inflows.** Payments that cash can't cover are refused, approval requests that would over-commit cash are refused, and no tool can add money.
4. **Least-privilege tools.** Each agent sees only the tools its role needs. Only Accounting can see payment tools; Customer Service can't see cash or invoices.
5. **Drafts only, never sent.** Customer messages and purchase orders are written to local JSON for a human to review. No tool can email, call, or reach a real vendor or customer.
6. **No made-up facts.** Every prompt requires facts from tools and "not in the database" when data is missing. Tools return errors instead of guesses.
7. **Customer privacy.** Messages never reveal costs, margins, cash, unpaid vendor bills, or other customers' information, and they go only to the ticket's requester.
8. **Full audit trail.** Every model response, tool call, tool result, delegation, and error is logged with who did it and why, and the log is append-only.
9. **Protected original data.** Agents work on `campus_customs_new.db`; the original is read only for resets, and resets happen before full runs.
10. **Clear escalation.** When a rule would be broken or a decision belongs to a human, agents set the ticket to `escalated` or `waiting_approval` instead of acting.

### Token-use limits

- **One budget per ticket.** The Boss and every delegated run share one usage counter: at most 40 model requests, 60 tool calls, and 250,000 total tokens per ticket. Going over stops the ticket.
- **Capped responses:** `max_tokens` 4,000 per model response, with one tool call at a time (no parallel fan-out).
- **Capped delegation:** at most 3 levels, no self-delegation, and no delegating back up the chain.
- **Retries capped at 2** per agent for bad tool calls or invalid output.
- **Prompts tell agents to keep it short:** 2-5 sentence summaries, one call per fact, no repeat calls, about 1-4 delegations per ticket, and stop when blocked.
- **Audit truncation:** tool outputs over 2,000 characters are clipped in the trail.

# Problem 7  -  Backend Routes

`backend/main.py` (FastAPI) runs on http://localhost:8000 and is started from `backend/` with `uvicorn main:app --reload --port 8000`. Ticket and cash data come through the MCP server. A new MCP tool, `list_tickets` (table: tickets), returns every ticket, including resolved ones.

- `GET /tickets` (http://localhost:8000/tickets): returns all three tickets with their status and whether each is open or resolved.
- `POST /tickets/{ticket_id}/run` (http://localhost:8000/tickets/101/run): runs the agent team on that ticket (Boss first) and returns the Boss's TicketDecision. Only one run at a time.
- `GET /events?limit=50&ticket_id=&run_id=` (http://localhost:8000/events): returns the most recent agent-loop events from output/audit_trail.json so the board can refresh.
- `GET /approvals` (http://localhost:8000/approvals): lists payment approval requests and purchase order drafts waiting on a human.
- `POST /approvals/{id}/approve` (http://localhost:8000/approvals/APR-001/approve, body `{"approved_by": "name"}`): after a human clicks approve, records the approval and then pays it through MCP `pay_bill`, which still refuses if cash is short. For a `PO-` id, it marks the purchase order approved, and it is never sent.
- `POST /approvals/{id}/deny` (http://localhost:8000/approvals/APR-001/deny, body `{"approved_by": "name"}`): a human denies a payment request or rejects a purchase order.
- `GET /cash` (http://localhost:8000/cash): returns the current checking balance from cash_accounts.
- `POST /reset` (http://localhost:8000/reset): restores data/campus_customs_new.db from the original and clears drafts and approvals. The audit trail is kept.
- `GET /health` (http://localhost:8000/health): a simple check that the server is up.

# Problem 8  -  Agent Dashboard

`frontend/` (React + Vite + TypeScript) runs at http://localhost:5173 with `npm run dev` and calls the backend at http://localhost:8000 (`frontend/.env.development`, `VITE_API_URL`). The backend's CORS allows the Vite origin (http://localhost:5173 and http://127.0.0.1:5173). The design is described in `output/design.md`.

Two routes were added for the board:
- `POST /tickets/{ticket_id}/resolve` (http://localhost:8000/tickets/101/resolve, body `{"resolved_by": "name"}`): a human marks the ticket resolved through MCP `update_ticket`.
- `GET /drafts` (http://localhost:8000/drafts): customer message and purchase order drafts (never sent), shown on the board.

# Problem 9  -  Resolve the Tickets (Final Harness)

## The run

- **Reset first:** `POST /reset` restored `data/campus_customs_new.db` from the original. The working DB matched the original byte for byte. **Starting checking: $3,400.00.**
- **Board runs** (all started with *Begin run* on the React board, http://localhost:5173):

| Ticket | Runs | Agents that worked | Human sign-offs (Casey Brengman) | Cash change | Final |
|---|---|---|---|---|---|
| 101 Tee, size S | 3 | Boss, Inventory, Accounting, Customer Service | APR-001 pay invoice 501 ($840); PO-005 restock (no cash) | -$840.00 | resolved (human) |
| 102 Rent | 1 | Boss, Facilities, Accounting, Customer Service | APR-002 pay rent ($2,400) | -$2,400.00 | resolved (human) |
| 103 Hoodies | 1 | Boss, Inventory, Accounting, Customer Service | none | $0.00 | resolved (Boss) |

- **Ending checking: $160.00** = $3,400 - $840 - $2,400. This matches `cash_accounts` and the 2 rows in `payments`.
- **Prompt fix during the run:** in run 2 of ticket 101, the Boss didn't request a purchase order once Bulldog was unblocked. We added that rule to `prompts/boss.md`, restarted the backend, and run 3 drafted PO-005.
- **Evidence:** `output/desk_tickets.html` (Actual sections + Cash tab), `output/resolved_tickets.json`, `output/resolved_board.html` (board screenshots, also in `output/board_images/`), `output/audit_trail.json` (306 events from the 5 real runs appended after the earlier test runs; nothing was wiped), `output/drafts.json`, `output/approvals.json`.

## Final Reference

### Tables (`data/campus_customs_new.db`)

| Table | Fields | Used by |
|---|---|---|
| desk | date_today, notes | Every agent ("today" = 2026-08-31) |
| inventory | sku, name, size, qty, location | Inventory, Accounting, Customer Service |
| pricing | sku, unit_cost, list_price | Accounting, Inventory, Customer Service |
| vendors | id, name, specialty, lead_days | Inventory, Accounting |
| leases | id, space_name, landlord, monthly_rent, next_due, notes | Facilities, Accounting |
| cash_accounts | name, balance, date | Accounting, Boss, dashboard |
| payments | id, kind, ref_id, amount, account, paid_at, approved_by | Accounting (written only by pay_bill) |
| invoices | id, vendor_id, amount, due_date, status, description | Accounting, Inventory |
| tickets | id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at | Boss, every agent, dashboard |

Local files (not shop tables): `output/drafts.json` (messages and POs, never sent), `output/approvals.json` (payment requests; only a human decides), `output/audit_trail.json` (append-only log).

### MCP tools (16, in `mcp_server/server.py`)

| Tool | Tables / files | Who can call it |
|---|---|---|
| get_shop_today | desk | all agents |
| list_tickets | tickets | backend (dashboard) |
| list_open_tickets | tickets | Boss, backend |
| get_ticket | tickets | all agents, backend |
| update_ticket | tickets | Boss, backend (Mark resolved) |
| check_stock_and_price | inventory, pricing | Inventory, Accounting, Customer Service |
| list_vendors | vendors, invoices, inventory, desk | Inventory |
| check_vendor_status | vendors, invoices, desk | Inventory, Accounting |
| draft_purchase_order | vendors, invoices, inventory, pricing, desk -> drafts.json | Inventory |
| get_cash_and_obligations | cash_accounts, invoices, leases, desk | Boss, Accounting, Facilities, backend |
| get_lease | leases, desk | Facilities |
| list_payments | payments | Accounting |
| request_payment_approval | invoices, leases, cash_accounts -> approvals.json | Accounting |
| get_approval_status | approvals.json | Boss, Accounting, Facilities |
| pay_bill | approvals.json, invoices, leases, cash_accounts, payments, desk | Accounting, backend (only after a human approves) |
| draft_customer_message | tickets -> drafts.json | Customer Service |

### The five agents (`backend/agents.py`, prompts in `backend/prompts/`)

All five run on `gpt-5.6-luna` through Portkey and return structured output (Boss: `TicketDecision`; specialists: `AgentReport`). Each one can `delegate` to any other agent, so they have full connectivity, with no self-delegation, no delegating back up the chain, and a maximum depth of 3.

| Agent | Role | Called on |
|---|---|---|
| Boss | Reads the ticket, routes it, makes the final call (including discounts), updates the ticket | 101, 102, 103 |
| Inventory | Stock by SKU and size, shortfalls, restock vendor, can-ship check, arrival dates, PO drafts | 101, 103 |
| Accounting | Cash, invoices, margins and floors, payment approval requests, pay after human approval | 101, 102, 103 |
| Facilities | Leases, rent, landlord notices | 102 |
| Customer Service | Honest customer and requester drafts, never sent | 101, 102, 103 |

### API routes (`backend/main.py`, http://localhost:8000)

- `GET /health`: checks that the server is up.
- `GET /tickets`: all tickets, with open or resolved.
- `POST /tickets/{id}/run`: runs the agent team on one ticket (one run at a time).
- `POST /tickets/{id}/resolve`: a human marks the ticket resolved (MCP update_ticket).
- `GET /events`: recent audit-trail events (filter by ticket_id or run_id).
- `GET /approvals`: payment requests and PO drafts.
- `POST /approvals/{id}/approve`: a human approves. For APR-, the approval is recorded and then MCP pay_bill runs. For PO-, the PO is marked approved and never sent.
- `POST /approvals/{id}/deny`: a human declines a payment or rejects a PO.
- `GET /drafts`: customer messages and PO drafts.
- `GET /cash`: the checking balance from cash_accounts.
- `POST /reset`: restores the working DB from the original and clears drafts and approvals. The audit trail is kept.

### Dashboard (`frontend/`, React + Vite + TypeScript, `npm run dev` -> http://localhost:5173)

A three-column "Agent Desk" in ink, paper, and maroon (details in `output/design.md`):
- **Left column:** Awaiting You (Approve & pay or Decline), Summary of the Boss's call and tool calls per agent, Drafts, and the Ledger.
- **Center:** the ticket header with *Begin run* and *Mark resolved*, a roster of the five agents (agents that weren't needed read "Not called"), and The Floor, a live feed of every agent step, polled every 1.5 seconds and indented by delegation depth.
- **Right column:** the Docket of tickets. Resolved tickets are struck through.
- **Masthead:** the Operator name (required for approvals and resolving) and the checking balance, which briefly turns maroon when it changes.
- `?ticket=N` opens the board on a specific ticket.

## All Safety Rules

### Shop rules (enforced in code, not just prompts)
1. **"Today" is `desk.date_today`.** All overdue and due-date math in the MCP tools uses it, never the real date.
2. **Lead times only from `vendors.lead_days`.**
3. **A vendor with an unpaid open invoice won't ship.** `check_vendor_status` reports `can_ship: false`, and `draft_purchase_order` refuses.
4. **Human approval for every payment.** Agents can only *request* approval. A human decides on the dashboard (or with `backend/approvals.py`), and `pay_bill` refuses anything not approved by a named human.
5. **An approved payment updates every related table** in one transaction: `payments`, `cash_accounts`, and `invoices.status` or `leases.next_due`.
6. **Never go negative.** `pay_bill` refuses if cash is short, and `request_payment_approval` refuses if pending plus approved requests would exceed cash.
7. **Cash only goes out.** No tool adds money, amounts must be positive, and revenue isn't modeled.
8. **Reset before a full run.** `POST /reset` restores the working copy, and the original DB is never written.
9. **Never contact real customers or vendors.** Messages and POs are only written to `output/drafts.json` and marked NOT sent. No tool can send email or place orders.
10. **Only gpt-5.6-luna** for agents, through Portkey. The API key is loaded from `.env` and never printed or committed.

### Guardrails for real customers and real money
- **Least-privilege tools per agent.** Only Accounting sees payment tools. Customer Service can't see cash or invoices.
- **Amounts come from the database, never from the agent.** If a bill changes after approval, the payment is refused.
- **Facts only from tools.** Prompts require "not in the database" instead of guessing.
- **Customer privacy.** Drafts may not mention cost, margin, cash, unpaid vendor bills, or other customers. *This run caught 2 drafts (MSG-001, MSG-004) that mentioned the invoice; the human review step is the backstop.*
- **Human closes tickets** that involved money or orders (*Mark resolved* requires an operator name).
- **Append-only audit trail.** Every model response, tool call, tool result, delegation, error, and token count is logged.
- **Clear escalation.** Agents use `waiting_approval` or `escalated` instead of acting when a human must decide.

### Token limits
- **One shared budget per ticket run** (Boss plus all delegations): 40 model requests, 60 tool calls, 250,000 tokens.
- **Per response:** `max_tokens` is 4,000. Delegation depth is capped at 3, with no loops. Retries are capped at 2.
- **Prompts ask for brevity:** one call per fact, 2-5 sentence summaries, about 1-4 delegations per ticket, and stop when blocked.
- **Audit outputs** are truncated at 2,000 characters.
- **Actual cost this run:** 5 board runs used 12-19 model requests and about 25-44k tokens each, all well under the caps.
