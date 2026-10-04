"""Run the Campus Customs agent team over the open tickets.

    python backend/team.py               # work every open ticket
    python backend/team.py --ticket 101  # work one ticket
    python backend/team.py --reset       # reset the working DB first (do this before a full run)

The reset copies data/campus_customs.db over data/campus_customs_new.db and clears
output/drafts.json and output/approvals.json. output/audit_trail.json is never wiped.
"""

import argparse
import asyncio
import json
import shutil
import uuid
from datetime import datetime

from agents import HW_DIR, CampusCustomsTeam, build_mcp_toolset

ORIGINAL_DB = HW_DIR / "data" / "campus_customs.db"
WORKING_DB = HW_DIR / "data" / "campus_customs_new.db"
RESET_FILES = (HW_DIR / "output" / "drafts.json", HW_DIR / "output" / "approvals.json")


def reset_database() -> None:
    """Restore the working copy from the original. The original is only ever read."""
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    for path in RESET_FILES:
        path.unlink(missing_ok=True)


async def run(ticket: int | None) -> list[dict]:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    toolset = build_mcp_toolset()
    async with toolset:
        team = CampusCustomsTeam(toolset)
        if ticket is None:
            listing = await toolset.direct_call_tool("list_open_tickets", {})
            ticket_ids = [t["id"] for t in listing["tickets"]]
        else:
            ticket_ids = [ticket]
        results = []
        for tid in ticket_ids:
            try:
                decision = await team.run_ticket(tid, run_id)
                results.append(decision.model_dump())
            except Exception as exc:
                results.append({"ticket_id": tid, "error": f"{type(exc).__name__}: {exc}"})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticket", type=int, help="work only this ticket id")
    parser.add_argument("--reset", action="store_true", help="reset the working DB from the original first")
    args = parser.parse_args()
    if args.reset:
        reset_database()
        print("Working database reset from the original.")
    print(json.dumps(asyncio.run(run(args.ticket)), indent=2))


if __name__ == "__main__":
    main()
