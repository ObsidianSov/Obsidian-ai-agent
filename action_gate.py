"""
Action Gate for Obsidian AI (ai.py)

Classifies shell commands into BLOCK / APPROVAL / ALLOW tiers before
they execute. This does NOT fully sandbox the shell (a determined
command can still find ways around string matching) — it is a safety
net against the agent running an obviously destructive command by
mistake or under a confused instruction, not a security boundary
against a malicious actor.

Pure functions only, no I/O — safe to import for testing without
triggering any side effects.
"""

import re

BLOCK_PATTERNS = [
    r"\bformat\s+[a-zA-Z]:",             # format C:
    r"\bdiskpart\b",                     # diskpart
    r"\bshutdown\b",                     # shutdown /s, shutdown -h
    r"\brm\s+-rf\s+/(\s|$)",             # rm -rf /
    r"\brd\s+/s\s+/q\s+[a-zA-Z]:\\?\s*$",  # rd /s /q C:\
    r"\bdel\s+/s\s+/q\s+[a-zA-Z]:\\?\*", # del /s /q C:\*
    r"\bmkfs\b",                         # mkfs.*
    r"\bdd\s+if=.*of=/dev/",             # dd if=... of=/dev/sdX
    r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:",  # fork bomb
    r"\bdrop\s+database\b",              # DROP DATABASE
]

APPROVAL_PATTERNS = [
    r"\bdel\b",
    r"\brm\b",
    r"\brmdir\b",
    r"\brd\b",
    r"\bgit\s+push\s+.*--force",
    r"\bgit\s+push\s+.*-f\b",
    r"\bgit\s+reset\s+--hard",
    r"\bgit\s+clean\s+-fd",
    r"\bdrop\s+table\b",
    r"\btruncate\s+table\b",
    r"\bchmod\s+777\b",
]


def classify_command(command: str):
    """
    Returns (tier, reason) where tier is 'BLOCK', 'APPROVAL', or 'ALLOW'.
    reason is None for ALLOW.
    """
    lowered = command.lower()

    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, lowered):
            return "BLOCK", f"matched blocked pattern: {pattern}"

    for pattern in APPROVAL_PATTERNS:
        if re.search(pattern, lowered):
            return "APPROVAL", f"matched approval-required pattern: {pattern}"

    return "ALLOW", None
