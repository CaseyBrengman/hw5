"""Human-only payment approvals. Agents can't run this; it is NOT an MCP tool.

    python backend/approvals.py list
    python backend/approvals.py approve APR-001 "Your Name"
    python backend/approvals.py deny APR-001 "Your Name"

After approval, re-run the ticket so Accounting can call pay_bill.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

APPROVALS_PATH = Path(__file__).resolve().parent.parent / "output" / "approvals.json"
DRAFTS_PATH = Path(__file__).resolve().parent.parent / "output" / "drafts.json"


def load() -> list[dict]:
    if not APPROVALS_PATH.exists() or not APPROVALS_PATH.read_text(encoding="utf-8").strip():
        return []
    return json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))


def decide(approval_id: str, approve: bool, human: str) -> dict:
    if not human.strip():
        raise ValueError("A human name is required.")
    approvals = load()
    for a in approvals:
        if a["approval_id"] == approval_id:
            if a["status"] != "pending":
                raise ValueError(f"{approval_id} is already '{a['status']}'.")
            a["status"] = "approved" if approve else "denied"
            a["decided_by"] = human.strip()
            a["decided_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            APPROVALS_PATH.write_text(json.dumps(approvals, indent=2), encoding="utf-8")
            return a
    raise ValueError(f"No approval with id={approval_id}.")


def decide_purchase_order(draft_id: str, approve: bool, human: str) -> dict:
    """A human approves or rejects a purchase order draft. Approving does NOT send it to the vendor."""
    if not human.strip():
        raise ValueError("A human name is required.")
    if not DRAFTS_PATH.exists():
        raise ValueError("No drafts exist.")
    drafts = json.loads(DRAFTS_PATH.read_text(encoding="utf-8"))
    for d in drafts:
        if d["draft_id"] == draft_id and d["kind"] == "purchase_order":
            if "approved" in d["status"] or "rejected" in d["status"]:
                raise ValueError(f"{draft_id} is already decided: {d['status']}.")
            d["status"] = ("approved by human - ready to order, NOT sent" if approve
                           else "rejected by human")
            d["decided_by"] = human.strip()
            d["decided_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            DRAFTS_PATH.write_text(json.dumps(drafts, indent=2), encoding="utf-8")
            return d
    raise ValueError(f"No purchase order draft with id={draft_id}.")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "list":
        print(json.dumps(load(), indent=2))
    elif len(sys.argv) == 4 and sys.argv[1] in ("approve", "deny"):
        print(json.dumps(decide(sys.argv[2], sys.argv[1] == "approve", sys.argv[3]), indent=2))
    else:
        print(__doc__)
