"""
Action Gate for Obsidian AI (ai.py)

Classifies shell commands into BLOCK / APPROVAL / ALLOW tiers before
they execute. This does NOT fully sandbox the shell (a determined
command can still find ways around string matching — e.g. an
environment variable that expands to an outside path) — it is a
safety net against the agent running an obviously destructive
command, or one that reaches outside its workspace, by mistake or
under a confused instruction. It is not a security boundary against
a malicious actor with full control of the input.

Pure functions only, no I/O — safe to import for testing without
triggering any side effects.
"""

import re
from pathlib import Path

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


def find_path_escapes(command: str, workspace_path: str):
    """
    Heuristic check for paths in a command that point outside the
    given workspace. Returns a list of human-readable reasons (empty
    if nothing suspicious was found). This is pattern-based, not a
    real path resolver — it will not catch every possible escape
    (e.g. an environment variable that expands to an outside path),
    but it catches the common, obvious ones: absolute paths, '..'
    traversal, and '~' home-directory shortcuts.
    """
    reasons = []
    workspace_norm = str(Path(workspace_path).resolve()).lower()

    if re.search(r"\.\.[/\\]", command) or re.search(r"\.\.\s*$", command):
        reasons.append("directory traversal ('..')")

    if re.search(r"(^|\s)~(?=[/\\]|\s|$)", command):
        reasons.append("home directory reference ('~')")

    # Windows-style absolute paths, e.g. C:\Users\...
    for match in re.finditer(r"\b([a-zA-Z]:[\\/][^\s\"']*)", command):
        path = match.group(1)
        if not path.lower().startswith(workspace_norm):
            reasons.append(f"absolute path outside workspace: {path}")

    # Unix-style absolute paths, e.g. /etc/passwd
    for match in re.finditer(r"(?:^|\s)(/[^\s\"']*)", command):
        path = match.group(1)
        if not path.lower().startswith(workspace_norm):
            reasons.append(f"absolute path outside workspace: {path}")

    return reasons


def classify_command(command: str, workspace_path: str = None):
    """
    Returns (tier, reason) where tier is 'BLOCK', 'APPROVAL', or 'ALLOW'.
    reason is None for ALLOW.

    workspace_path is optional for backward compatibility (existing
    callers/tests that don't pass it just skip the path-escape check).
    Pass it whenever the real workspace root is known, so commands
    reaching outside it get caught.
    """
    lowered = command.lower()

    for pattern in BLOCK_PATTERNS:
        if re.search(pattern, lowered):
            return "BLOCK", f"matched blocked pattern: {pattern}"

    if workspace_path:
        escapes = find_path_escapes(command, workspace_path)
        if escapes:
            return "APPROVAL", f"references path(s) outside the workspace: {'; '.join(escapes)}"

    for pattern in APPROVAL_PATTERNS:
        if re.search(pattern, lowered):
            return "APPROVAL", f"matched approval-required pattern: {pattern}"

    return "ALLOW", None
