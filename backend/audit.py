"""Append-only audit trail at output/audit_trail.json.

Every agent-loop step is appended as it happens. Earlier runs are never wiped.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

from models import AuditEvent, TeamDeps

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
MAX_TEXT = 2000  # long tool outputs are truncated so the trail stays readable
_lock = threading.Lock()


def _clip(value):
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + f"... [truncated {len(text) - MAX_TEXT} chars]"


def log_event(deps: TeamDeps, step: int, event: str, detail: dict, tokens: dict | None = None) -> None:
    entry = AuditEvent(
        timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
        run_id=deps.run_id,
        ticket_id=deps.ticket_id,
        agent=deps.agent,
        depth=deps.depth,
        chain=list(deps.chain),
        step=step,
        event=event,
        detail={k: _clip(v) if k in ("content", "output", "args", "text") else v for k, v in detail.items()},
        tokens=tokens,
    )
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        trail = []
        if AUDIT_PATH.exists() and AUDIT_PATH.read_text(encoding="utf-8").strip():
            trail = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        trail.append(entry.model_dump())
        AUDIT_PATH.write_text(json.dumps(trail, indent=2), encoding="utf-8")
