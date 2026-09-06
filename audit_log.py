"""
Audit Log for Obsidian AI (ai.py)

Records every tool call to a durable JSON-lines file: one JSON
object per line, appended, never rewritten. Logs regardless of
success or failure, and regardless of Action Gate outcome, so
there is always a complete record of what the agent attempted.

Pure logging logic, safely importable for testing without
triggering any side effects beyond writing to the given path.
"""

from pathlib import Path
from datetime import datetime
import json


class AuditLog:
    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "audit_log.jsonl"

    def record(self, tool_name: str, arguments: dict, success: bool,
               output: str, tier: str = None):
        """
        Append one entry. Never raises — a logging failure should
        never be allowed to break the tool call it's recording.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            "tier": tier,
            "success": success,
            "output_snippet": (output or "")[:300],
        }

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            # Logging must never crash the agent's actual work.
            pass

    def read_all(self):
        """Read back every logged entry, oldest first. For tests/inspection."""
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    def tail(self, n: int = 10):
        """Most recent n entries."""
        return self.read_all()[-n:]
