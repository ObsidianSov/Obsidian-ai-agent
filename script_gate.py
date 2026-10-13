"""
Script Gate for Obsidian AI (ai.py)  —  Milestone 6

Problem: the agent can write a script with write_file and then run it
(`python x.py`, `bash x.sh`, `node x.js`). The Action Gate only sees the
short command, not what is inside the script, so a script could do
anything the command line could, with no approval.

Fix: before a command runs, find every script file it would execute.
Each script must be approved by the human first (the prompt shows the
code). An approval is remembered for the session, but ONLY for the
exact content: if the script, or any other file of the same type in the
same folder (it may import them), changes, you are asked again.

Always asks (and does not remember the answer) when the script cannot
be pinned down: path built from a variable/wildcard/~, a `cd` earlier in
the command, a script outside the workspace, a whole folder, a script
fed through stdin/heredoc, a script that may be created by the same
command, or too many files to fingerprint.

NOT covered (be honest about it):
  - code the script imports from OTHER folders or packages
  - `npm run`, `make`, `pip install` (setup.py), `python -m pytest`
    when the module is not a file in the workspace
  - shell tricks the simple parser can't follow ($(...), backticks
    building a command, aliases, functions)
This is a safety net against a confused agent and a speed bump for a
tricked one. It is not a sandbox. It also only protects you if you
actually read the code in the prompt.

Functions are written so they can be tested without ai.py: the prompt
(`ask`) and printing (`out`) are passed in.
"""

import hashlib
import os
import re
import shlex
from pathlib import Path

INTERPRETER_RE = re.compile(
    r"^(python[0-9.]*|py|pypy3?|node|nodejs|deno|bun|bash|sh|zsh|dash|ksh|"
    r"perl|ruby|php|lua|rscript)$"
)
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
WRAPPERS = {"sudo", "time", "nohup", "exec", "command", "env", "nice",
            "timeout", "xargs", "stdbuf", "setsid", "builtin"}
EXEC_FLAGS = {"-exec", "-execdir", "-ok", "-okdir"}
INLINE_FLAGS = {"-c", "-e", "-p"}
VALUE_FLAGS = {"-W", "-X", "-o", "-O", "-r", "-I", "--require"}
CD_COMMANDS = {"cd", "pushd", "popd"}

ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
NUMERIC_RE = re.compile(r"^[0-9.]+[smhd]?$")
MODULE_RE = re.compile(r"^[A-Za-z0-9_.]+$")
UNRESOLVABLE_CHARS = set("$`~*?[]{}()<>|&;!\"'\\")

STDIN_NOTE = "script supplied through stdin or a heredoc (can't be inspected ahead of time)"
CD_MARK = "__CD__"

MAX_FINGERPRINT_FILES = 200
MAX_FINGERPRINT_BYTES = 5_000_000
PREVIEW_LINES = 40
VIEW_MAX_CHARS = 8000


# ------------------------------------------------------------
# Parsing a command line (pure)
# ------------------------------------------------------------

def _split_segments(command: str):
    """Split on ; & | and newlines that are not inside quotes."""
    segments, buf, quote, i = [], [], None, 0
    while i < len(command):
        ch = command[i]
        if ch == "\\" and quote != "'" and i + 1 < len(command):
            buf.append(ch)
            buf.append(command[i + 1])
            i += 2
            continue
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch in ";&|\n":
            segments.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def _tokenize(segment: str):
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()   # unbalanced quotes: still look for interpreters


def _parse_interpreter_args(base, tokens, j, found, notes, depth):
    """Read the arguments after an interpreter name. Returns next index."""
    is_shell = base in SHELLS
    while j < len(tokens):
        a = tokens[j]
        if a == "--":
            j += 1
            continue
        if a == "-m" and j + 1 < len(tokens):
            found.append(("module", tokens[j + 1]))
            return len(tokens)
        if a in INLINE_FLAGS:
            if is_shell and j + 1 < len(tokens) and depth < 3:
                f2, n2 = extract_script_targets(tokens[j + 1], depth + 1)
                found.extend(f2)
                notes.extend(n2)
            return len(tokens)
        if a in VALUE_FLAGS:
            j += 2
            continue
        if a == "-":
            notes.append(STDIN_NOTE)
            return len(tokens)
        if a == "<":
            if j + 1 < len(tokens):
                found.append(("file", tokens[j + 1]))
            return len(tokens)
        if a.startswith("<<"):
            notes.append(STDIN_NOTE)
            return len(tokens)
        if a.startswith("<"):
            found.append(("file", a[1:]))
            return len(tokens)
        if a.startswith("-"):
            j += 1
            continue
        found.append(("file", a))
        return len(tokens)
    return j


def _parse_tokens(tokens, found, notes, depth):
    at_cmd = True
    i = 0
    while i < len(tokens):
        tok = tokens[i].lstrip("({")
        if not tok:
            i += 1
            continue
        if tok in EXEC_FLAGS:
            at_cmd = True
            i += 1
            continue
        if not at_cmd:
            i += 1
            continue
        base = os.path.basename(tok).lower()
        if ASSIGN_RE.match(tok):
            i += 1
            continue
        if base in WRAPPERS:
            i += 1
            while i < len(tokens) and (tokens[i].startswith("-") or NUMERIC_RE.match(tokens[i])):
                i += 1
            continue
        if base in CD_COMMANDS:
            notes.append(CD_MARK)
            at_cmd = False
            i += 1
            continue
        if tok in ("source", "."):
            if i + 1 < len(tokens):
                found.append(("file", tokens[i + 1]))
            at_cmd = False
            i += 2
            continue
        if INTERPRETER_RE.match(base):
            i = _parse_interpreter_args(base, tokens, i + 1, found, notes, depth)
            at_cmd = False
            continue
        if tok.startswith(("./", "../")):
            found.append(("file", tok))
        at_cmd = False
        i += 1


def extract_script_targets(command: str, depth: int = 0):
    """
    Returns (targets, notes).
    targets: list of ("file", path_text) or ("module", dotted_name)
    notes:   list of reasons that need approval but have no file to show
    """
    found, notes = [], []
    for segment in _split_segments(command):
        _parse_tokens(_tokenize(segment), found, notes, depth)
    return found, notes


# ------------------------------------------------------------
# Looking at the files (reads the disk, changes nothing)
# ------------------------------------------------------------

def fingerprint_script(path):
    """
    Returns (fingerprint or None, number_of_sibling_files_covered).
    The fingerprint covers the script AND every other file with the same
    extension in the same folder, so editing a helper it imports
    invalidates the approval. None = too big/many/unreadable.
    """
    path = Path(path)
    try:
        siblings = sorted(
            p for p in path.parent.iterdir()
            if p.is_file() and p != path and p.suffix == path.suffix
        )
        if len(siblings) > MAX_FINGERPRINT_FILES:
            return None, len(siblings)
        h = hashlib.sha256()
        h.update(str(path).encode())
        total = 0
        for p in [path] + siblings:
            data = p.read_bytes()
            total += len(data)
            if total > MAX_FINGERPRINT_BYTES:
                return None, len(siblings)
            h.update(b"\0" + p.name.encode() + b"\0")
            h.update(hashlib.sha256(data).digest())
        return h.hexdigest(), len(siblings)
    except OSError:
        return None, 0


def _inside(path: Path, workspace: Path) -> bool:
    try:
        path.relative_to(workspace)
        return True
    except ValueError:
        return False


def _resolve(kind, value, workspace: Path, cd_seen: bool):
    """Returns (path or None, problem or None). problem: 'unresolvable' | 'missing'."""
    if kind == "module":
        if not MODULE_RE.match(value):
            return None, "unresolvable"
        rel = value.replace(".", "/")
        for candidate in (workspace / f"{rel}.py", workspace / rel / "__main__.py"):
            if candidate.is_file():
                return candidate.resolve(), None
        return None, "missing"
    if not value or any(c in UNRESOLVABLE_CHARS for c in value) or "\x00" in value:
        return None, "unresolvable"
    p = Path(value)
    if not p.is_absolute():
        if cd_seen:
            return None, "unresolvable"
        p = workspace / p
    try:
        return p.resolve(), None
    except (OSError, RuntimeError):
        return None, "unresolvable"


def _preview(path: Path, nsiblings: int):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(could not read the file)"
    lines = text.splitlines()
    shown = [f"{n:>3}| {line[:160]}" for n, line in enumerate(lines[:PREVIEW_LINES], 1)]
    head = f"{len(lines)} lines, {len(text.encode('utf-8', 'replace'))} bytes"
    if nsiblings:
        head += f"; approval also covers {nsiblings} other '{path.suffix or 'extensionless'}' file(s) in this folder"
    out = [head] + shown
    if len(lines) > PREVIEW_LINES:
        out.append(f"... {len(lines) - PREVIEW_LINES} more lines (type view to see more)")
    return "\n".join(out)


def find_scripts_needing_approval(command: str, workspace, approved: set):
    """
    Returns a list of dicts: display, path, fingerprint, reason, preview.
    Empty list = nothing needs asking. `approved` is the session's set of
    fingerprints the human has already said yes to.
    """
    ws = Path(workspace).resolve()
    targets, notes = extract_script_targets(command)
    cd_seen = CD_MARK in notes
    notes = [n for n in dict.fromkeys(notes) if n != CD_MARK]
    multi_step = len(_split_segments(command)) > 1 or any(c in command for c in "<>")

    items = []
    for note in notes:
        items.append({"display": "(no file)", "path": None, "fingerprint": None,
                      "reason": note, "preview": None})

    seen = set()
    for kind, value in targets:
        if (kind, value) in seen:
            continue
        seen.add((kind, value))
        path, problem = _resolve(kind, value, ws, cd_seen)

        if problem == "unresolvable":
            why = ("a 'cd' earlier in the command means the script's real location can't be worked out"
                   if cd_seen and value and not any(c in UNRESOLVABLE_CHARS for c in value)
                   else "script path uses a variable, wildcard, ~ or other trick, so it can't be checked ahead of time")
            items.append({"display": value, "path": None, "fingerprint": None,
                          "reason": why, "preview": None})
            continue
        if problem == "missing":
            continue   # a module that isn't workspace code (pytest, pip...) — not covered, see docstring

        shown = str(path.relative_to(ws)) if _inside(path, ws) else str(path)

        if not path.exists():
            if multi_step:
                items.append({"display": shown, "path": None, "fingerprint": None,
                              "reason": "script does not exist yet; this command may create it and run it in one step",
                              "preview": None})
            continue   # a lone run of a missing file just fails

        if path.is_dir():
            items.append({"display": shown, "path": None, "fingerprint": None,
                          "reason": "runs a whole folder/package", "preview": None})
            continue

        fp, nsib = fingerprint_script(path)
        if not _inside(path, ws):
            reason, fp = "script is OUTSIDE the workspace", None
        elif fp is None:
            reason = "too many/large files to fingerprint; this approval will not be remembered"
        else:
            if fp in approved:
                continue
            reason = "script has not been approved yet (or its content changed)"
        items.append({"display": shown, "path": path, "fingerprint": fp,
                      "reason": reason, "preview": _preview(path, nsib)})
    return items


def _denial(display: str) -> str:
    # Written for the MODEL: it must stop, not retry or work around.
    return (f"DENIED: The user refused to let this script run ({display}). "
            "It was NOT executed. Do not retry this command or run the script "
            "in any other way. Stop, tell the user it was denied, and ask "
            "what they want to do instead.")


def review_command(command: str, workspace, approved: set, ask=None, out=print, denied=None):
    """
    Ask the human about every script the command would run.
    Returns None if the command may run, or a "DENIED: ..." string.

    `denied` is the set of scripts the human already said NO to during
    the current request. The same script is not asked about again (the
    model tends to retry a denied command); the caller clears the set
    when the human sends a new message.
    """
    ask = ask or input   # looked up now (not at import) so tests can replace input()
    if denied is None:
        denied = set()
    for item in find_scripts_needing_approval(command, workspace, approved):
        key = item["fingerprint"] or f"{item['reason']}|{item['display']}"
        if key in denied:
            out("\n[SCRIPT GATE] You already said no to this script for this request — not asking again.")
            return _denial(item["display"])
        out(f"\n[SCRIPT GATE] APPROVAL REQUIRED — {item['reason']}")
        out(f"Script: {item['display']}")
        if item["preview"]:
            out(item["preview"])

        while True:
            try:
                answer = ask("Run this script? (yes/no/view): ").strip().lower()
            except EOFError:
                answer = "no"
            if answer in ("view", "v"):
                if item["path"]:
                    text = Path(item["path"]).read_text(encoding="utf-8", errors="replace")
                    out(text[:VIEW_MAX_CHARS] + ("\n... (cut off)" if len(text) > VIEW_MAX_CHARS else ""))
                else:
                    out("(no file to show)")
                continue
            break

        if answer in ("yes", "y"):
            if item["fingerprint"]:
                approved.add(item["fingerprint"])
            out("[SCRIPT GATE] Approved by user.")
            continue

        out("[SCRIPT GATE] Denied by user.")
        denied.add(key)
        return _denial(item["display"])
    return None
