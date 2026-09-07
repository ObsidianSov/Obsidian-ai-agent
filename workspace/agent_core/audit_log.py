"""
Audit Log - Phase 6

Records every tool action the agent takes to a durable, timestamped
JSON-lines file, independent of terminal scrollback. This is the record
you check after any crash, power loss, or "what did it actually do"
question - one file, not a screenshot reconstruction.
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional


class AuditLog:
    """
    Appends one JSON line per tool action to a log file.
    """

    def __init__(self, log_path: Optional[str] = None):
        workspace = os.environ.get('OBSIDIAN_WORKSPACE', os.getcwd())
        self.log_path = log_path or os.path.join(workspace, "obsidian_audit.log")

    def record(
        self,
        action: str,
        action_input: Dict[str, Any],
        tier: str,
        success: bool,
        output: str = "",
        error: Optional[str] = None,
        duration: float = 0.0
    ) -> None:
        """Append one entry. Never raises - a logging failure must not break the agent."""
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "input": action_input,
            "tier": tier,
            "success": success,
            "duration": round(duration, 4),
            "output": (output or "")[:300],
        }
        if error:
            entry["error"] = error

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def tail(self, n: int = 20) -> str:
        """Return the last n log entries as formatted text, for quick review."""
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()[-n:]
            return "".join(lines)
        except FileNotFoundError:
            return "(no audit log yet)"
