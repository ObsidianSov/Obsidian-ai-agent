"""
Task Engine v1 for Obsidian AI  —  Milestone 8

THE PROBLEM: until now, "look before you build" was only a request in the
system prompt. A model could ignore it and start writing files or running
commands on a guess. Earlier sessions produced code that was never run
for exactly this reason.

THE FIX: every request from the human starts in the INSPECT phase, and the
PROGRAM (not the model) enforces it:

  INSPECT  only read-only tools work (list, read, search, recall, and a
           short list of read-only commands such as ls / cat / grep).
           write_file, create_directory and every other command are LOCKED.
  (plan)   the model calls submit_plan. The human sees the plan and
           answers yes or no.
  ACT      after a "yes" every tool unlocks. The Action Gate and the
           script gate still apply exactly as before.

A new message from the human resets everything to INSPECT. The human can
skip the plan for one request by starting the message with "/do ".

Requests that need no changes (a question, an explanation) are never
blocked: the model simply answers in text.

Pure logic, no file or network access. The approval prompt is passed in,
so tests can answer it. Safe to import anywhere.
"""

import re
import shlex

INSPECT = "INSPECT"
ACT = "ACT"

# Tools that never change project files. Anything NOT listed here is locked
# in the INSPECT phase, so a tool added later is locked until someone decides
# it is safe (default deny). run_command is handled separately below.
READ_ONLY_TOOLS = frozenset({
    "list_files",
    "read_file",
    "fetch_url",
    "web_search",
    "recall_memory",
    "remember",      # writes agent memory, not project files
    "submit_plan",
})

# ----------------------------------------------------------------------
# Read-only commands
# ----------------------------------------------------------------------

_PLAIN_READERS = frozenset({
    "ls", "cat", "head", "tail", "wc", "pwd", "grep", "du", "df",
    "stat", "file", "which",
})
_VERSION_FLAGS = {
    "python": {"--version", "-V"},
    "python3": {"--version", "-V"},
    "pip": {"--version", "-V"},
    "node": {"--version", "-v"},
    "npm": {"--version", "-v"},
}
_GIT_READ_ONLY = frozenset({"status", "log", "diff", "show", "ls-files", "rev-parse"})
_FIND_FORBIDDEN = frozenset({
    "-delete", "-exec", "-execdir", "-ok", "-okdir",
    "-fprint", "-fprintf", "-fprint0", "-fls",
})
_TAIL_FOLLOW = frozenset({"-f", "-F", "--follow"})


def _tokens(command):
    """Split a command into tokens; pipes and operators become their own tokens."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _drop_harmless_redirects(tokens):
    """
    Remove redirects that only throw output away (>/dev/null, 2>/dev/null,
    2>&1). They cannot write a file, and models add them constantly.
    Every other redirect stays in place and makes the command not read-only.
    """
    out, i = [], 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if (tok == ">" and nxt == "/dev/null") or (tok == ">&" and nxt in ("1", "2")):
            if out and out[-1] in ("1", "2"):
                out.pop()
            i += 2
            continue
        out.append(tok)
        i += 1
    return out


def _segment_is_read_only(tokens):
    if not tokens:
        return False
    cmd, args = tokens[0], tokens[1:]

    if cmd in _PLAIN_READERS:
        if cmd == "tail" and any(a in _TAIL_FOLLOW for a in args):
            return False  # follows forever
        return True

    if cmd == "find":
        return not any(a in _FIND_FORBIDDEN for a in args)

    if cmd == "git":
        if not args or args[0] not in _GIT_READ_ONLY:
            return False
        return not any(a.startswith("--output") for a in args)

    if cmd in _VERSION_FLAGS:
        return len(args) == 1 and args[0] in _VERSION_FLAGS[cmd]

    return False


def is_read_only_command(command):
    """
    True only when the command is a simple read-only one. Strict on purpose:
    when in doubt it says False and the command waits for plan approval.
    Pipes between read-only commands are fine. Redirects, chaining,
    backgrounding, substitutions and anything that can write are not.
    """
    if not isinstance(command, str) or not command.strip():
        return False
    if any(ch in command for ch in ("`", "\n", "\r")) or "$(" in command:
        return False

    try:
        tokens = _tokens(command)
    except ValueError:      # unbalanced quotes etc.
        return False
    tokens = _drop_harmless_redirects(tokens)
    if not tokens:
        return False

    segments, current = [], []
    for tok in tokens:
        if tok == "|":
            segments.append(current)
            current = []
        elif re.fullmatch(r"[();<>|&]+", tok):
            return False    # redirect, ;, &, &&, ||, subshell ...
        else:
            current.append(tok)
    segments.append(current)

    return all(_segment_is_read_only(seg) for seg in segments)


# ----------------------------------------------------------------------
# Plans
# ----------------------------------------------------------------------

MAX_STEPS = 15
MAX_FILES = 30
MAX_TEXT = 400


def _clean_text(value):
    """Make model-written text safe to print: no escape codes or control characters."""
    text = "".join(ch for ch in str(value) if ch == "\n" or (ch >= " " and ch != "\x7f"))
    return text.strip()


def validate_plan(arguments):
    """Return (plan_dict, None) or (None, problem_text)."""
    if not isinstance(arguments, dict):
        return None, "the plan must be an object with 'summary' and 'steps'"

    summary = arguments.get("summary")
    if not isinstance(summary, str) or not _clean_text(summary):
        return None, "'summary' must be a short, non-empty sentence"

    steps = arguments.get("steps")
    if not isinstance(steps, list) or not steps:
        return None, "'steps' must be a non-empty list of strings"
    if len(steps) > MAX_STEPS:
        return None, f"'steps' has {len(steps)} items; keep it to {MAX_STEPS} or fewer"
    if not all(isinstance(s, str) and _clean_text(s) for s in steps):
        return None, "every step must be a non-empty string"

    files = arguments.get("files", [])
    if files is None:
        files = []
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        return None, "'files' must be a list of file paths (strings)"
    if len(files) > MAX_FILES:
        return None, f"'files' has {len(files)} items; keep it to {MAX_FILES} or fewer"

    return {
        "summary": _clean_text(summary)[:MAX_TEXT],
        "steps": [_clean_text(s)[:MAX_TEXT] for s in steps],
        "files": [_clean_text(f)[:MAX_TEXT] for f in files if _clean_text(f)],
    }, None


def format_plan(plan):
    lines = ["", "=" * 60, "PLAN FROM OBSIDIAN AI", "=" * 60, f"Goal: {plan['summary']}", "", "Steps:"]
    lines += [f"  {i}. {step}" for i, step in enumerate(plan["steps"], 1)]
    if plan["files"]:
        lines += ["", "Files it expects to create or change:"]
        lines += [f"  - {f}" for f in plan["files"]]
    lines += ["=" * 60]
    return "\n".join(lines)


def parse_do_prefix(text):
    """
    "/do fix the button" -> ("fix the button", True): the human skips the
    plan step for this one request. Anything else -> (text, False).
    """
    if not isinstance(text, str):
        return text, False
    stripped = text.strip()
    match = re.match(r"(?i)^/do(?:\s+(.*))?$", stripped, re.S)
    if match:
        return (match.group(1) or "").strip(), True
    return text, False


# ----------------------------------------------------------------------
# The engine
# ----------------------------------------------------------------------

LOCKED_MESSAGE = (
    "LOCKED: Nothing was changed. You are in the INSPECT phase for this "
    "request, so only read-only tools are allowed (list_files, read_file, "
    "fetch_url, web_search, recall_memory, and read-only commands such as "
    "ls, cat, grep). Look around first, then call submit_plan with a short "
    "summary, your steps, and the files you expect to touch. The human must "
    "approve the plan before you can write files or run other commands. "
    "If this request needs no changes, just answer in text."
)

REJECTED_MESSAGE = (
    "LOCKED: The human rejected your plan for this request. Do not write "
    "files or run commands. Tell the human, in one or two sentences, what "
    "you would change or what you need to know, then stop and wait for "
    "their next message."
)


class TaskState:
    def __init__(self):
        self.reset()

    def reset(self, start_in_act=False):
        """Call this every time the human types a new message."""
        self.phase = ACT if start_in_act else INSPECT
        self.plan = None
        self.plan_rejected = False

    def check_tool(self, name, arguments):
        """None if the tool may run now, otherwise the text to send the model."""
        if self.phase == ACT:
            return None
        if name == "run_command":
            command = arguments.get("command") if isinstance(arguments, dict) else None
            if is_read_only_command(command):
                return None
        elif name in READ_ONLY_TOOLS:
            return None
        return REJECTED_MESSAGE if self.plan_rejected else LOCKED_MESSAGE

    def submit_plan(self, arguments, ask, show=print):
        """
        Show the plan to the human and wait for yes/no. `ask` is the prompt
        function (ask_human in ai.py). Returns the text for the model.
        """
        if self.phase == ACT:
            return "No plan needed: this request is already approved for action. Continue with the work."
        if self.plan_rejected:
            return REJECTED_MESSAGE

        plan, problem = validate_plan(arguments)
        if problem:
            return f"INVALID PLAN: {problem}. Call submit_plan again with a valid plan."

        show(format_plan(plan))
        try:
            answer = ask("Approve this plan? (yes/no, or type what to change): ").strip()
        except EOFError:
            answer = "no"

        lowered = answer.lower()
        if lowered in ("yes", "y"):
            self.phase = ACT
            self.plan = plan
            show("[TASK ENGINE] Plan approved. Tools unlocked for this request.")
            return (
                "PLAN APPROVED by the human. All tools are now unlocked for this "
                "request (the safety gates still apply). Follow the plan. If it "
                "must change, tell the human before you change course."
            )

        if lowered in ("", "no", "n"):
            self.plan_rejected = True
            show("[TASK ENGINE] Plan rejected. Still locked.")
            return REJECTED_MESSAGE

        # Anything else is the human's feedback: let the model revise.
        show("[TASK ENGINE] Plan not approved. Feedback sent back to the model.")
        return (
            "PLAN NOT APPROVED. Still locked. The human wrote: "
            f"{_clean_text(answer)[:MAX_TEXT]!r}. Revise the plan to address "
            "this and call submit_plan again, or ask a question."
        )
