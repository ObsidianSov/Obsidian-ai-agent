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

Scripts the agent writes itself and then runs are handled by
script_gate.py (M6): the human approves the script's content before it
runs. That gate has its own documented limits. As a second layer,
run_command() starts every command with scrubbed_env() so API keys and
tokens are simply not present in the child process. A real sandbox is a
later milestone.

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

# (regex, plain-English label). Checked after APPROVAL_PATTERNS. These cover
# ways around the simple patterns above that a confused or tricked agent
# could use: deleting via find, running inline code, piping downloads into a
# shell, and reading secrets.
RISKY_PATTERNS = [
    (r"\bfind\b[^|;&]*\s-delete\b", "find -delete removes files"),
    (r"\b(python[0-9.]*|py|node|nodejs|perl|ruby|php)\s+-[ce]\b",
     "inline code passed straight to an interpreter"),
    (r"\|\s*(sudo\s+)?(sh|bash|zsh|dash|ksh)\b",
     "output piped into a shell"),
    (r"\|\s*(python[0-9.]*|perl|ruby|node)\s*(-\s*)?($|[;&|])",
     "output piped into an interpreter as code"),
    (r"<\(\s*(curl|wget)\b", "downloaded script run through process substitution"),
    (r"\beval\b", "eval runs text as code"),
    (r"\bbase64\s+(-d|--decode)\b", "decoding hidden text (often used to disguise commands)"),
    (r"(^|[;&|]\s*)(env|printenv|export|set)\s*($|[|;&>])",
     "lists environment variables (can reveal secrets)"),
    (r"\bprintenv\s+\S", "reads a specific environment variable"),
    (r"\$\{?\w*(key|token|secret|passw(or)?d|credential)\w*\}?",
     "references a secret-looking variable"),
    (r"(^|[\s/\"'])\.env\b", "touches a .env file (secrets)"),
    (r"\.ssh\b|\bid_rsa\b|\.netrc\b|\.git-credentials\b", "touches credential files"),
    (r"\bkillswitch\b", "touches the kill switch"),
]

# Environment variables whose names look like secrets are removed before any
# command runs, so a command cannot print or send them.
SECRET_NAME_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTH")
SECRET_NAME_PREFIXES = ("OPENROUTER", "GOOGLE", "OPENAI", "ANTHROPIC", "GITHUB", "GH_", "AWS_", "AZURE_")


def scrubbed_env(env):
    """
    Return a copy of `env` (a mapping such as os.environ) without anything
    that looks like a secret. The original mapping is not modified.
    """
    clean = {}
    for name, value in env.items():
        upper = name.upper()
        if any(hint in upper for hint in SECRET_NAME_HINTS):
            continue
        if upper.startswith(SECRET_NAME_PREFIXES):
            continue
        clean[name] = value
    return clean


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

    for pattern, label in RISKY_PATTERNS:
        if re.search(pattern, lowered):
            return "APPROVAL", f"risky command: {label}"

    return "ALLOW", None
