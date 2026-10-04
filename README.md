# Campus Customs Agent Desk (Homework 5)

A five-agent team that works the Campus Customs shop's tickets. It is made of three parts:

1. **MCP server** (`mcp_server/`, FastMCP): the only way agents read or change shop data. 16 tools over `data/campus_customs_new.db`.
2. **FastAPI backend** (`backend/`): five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service) on `gpt-5.6-luna` through Portkey. Every agent can delegate to every other agent, and every step is logged to an append-only audit trail.
3. **React dashboard** (`frontend/`, Vite + TypeScript): a human watches the agents work, approves payments, and marks tickets resolved.

## Where to look (for graders)

| Problem | Deliverable |
|---|---|
| 1 | `AI_prompts.md`: every prompt, timestamped, with notes |
| 2 | `output/harness.md` (Problem 2 section: table notes and ticket links) |
| 3 | `mcp_server/server.py`, `mcp_server/README.md`, `output/harness.md` (Problem 3) |
| 4 | `.mcp.json`, `output/mcp_smoke.json` |
| 5 | `backend/agents.py`, `backend/models.py`, `backend/prompts/*.md`, `output/audit_trail.json`, `output/harness.md` (Problem 5: agents, tools, safety) |
| 6 | `output/desk_tickets.html` (Expected sections) |
| 7 | `backend/main.py`, `output/harness.md` (Problem 7: routes) |
| 8 | `frontend/`, `output/design.md` |
| 9 | `output/desk_tickets.html` (Actual + Cash tabs), `output/resolved_tickets.json`, `output/resolved_board.html`, `output/harness.md` (final reference) |
| 10 | `output/desk_tickets.html` (Reflection tab) |
| 11 | This repo, `output/github_url.txt` |

The `.html` files open with a double-click; no server is needed.

## Layout

```
AI_prompts.md          prompt log for every problem
requirements.txt       Python dependencies
.env.example           copy to .env and add PORTKEY_API_KEY (the real .env is not committed)
.mcp.json              registers the MCP server with a vibe coder (Claude Code)
data/
  campus_customs.db      original database (never modified)
  campus_customs_new.db  working copy (the state after the Problem 9 run: all tickets resolved, $160 checking)
mcp_server/            FastMCP server (server.py) + README
backend/               FastAPI app (main.py), agents (agents.py), data types (models.py),
                       audit trail (audit.py), CLI runner (team.py), human approvals (approvals.py),
                       prompts/ (one prompt per agent)
frontend/              React + Vite + TypeScript dashboard
output/                harness, evidence, and reports (board_images/ holds the board screenshots;
                       drafts.json and approvals.json are the local drafts and approval records)
```

## Run it

Requires Python 3.12+ and Node 20+.

```bash
pip install -r requirements.txt
cp .env.example .env        # then add your PORTKEY_API_KEY
```

Backend (from `backend/`):

```bash
uvicorn main:app --reload --port 8000
```

Dashboard (from `frontend/`):

```bash
npm install
npm run dev                 # http://localhost:5173, talks to http://localhost:8000
```

Click **Reset to original data** on the board (or `POST /reset`) before a fresh run, then pick a ticket and click **Begin run**. Payments wait in **Awaiting You** until a human approves them.

## Shop rules the system enforces

- "Today" is `desk.date_today` (2026-08-31). Lead times come from `vendors.lead_days`.
- A vendor with an unpaid open invoice won't ship.
- No payment without explicit human approval. The pay tool refuses anything that would make cash negative, and cash only goes out.
- The database is reset to the original before a full run, and the original is never modified.
- Customer and vendor messages are local drafts only (`output/drafts.json`) and are never sent.

Full details: `output/harness.md`.
