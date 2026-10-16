"""
Verify step v1 for Obsidian AI  -  Milestone 9

THE PROBLEM: a model can write a file and then say "Done!" without ever
checking that the file exists, runs, or works. Earlier sessions produced
"finished" work that had never been run.

THE FIX: the PROGRAM (not the model) keeps a list of the files the agent
wrote during this request. When the model tries to give its final answer
and some of those files have no passing check AFTER their last write, the
answer is held back and the model is sent back to check. After 2 bounces
the answer is shown anyway, with a program-written NOT VERIFIED notice the
model cannot hide or reword.

What counts as a check (after the file's last write):
  * Code files (.py .js .mjs .sh): a command that RUNS or tests that file
    and exits with code 0, for example `python hello.py`,
    `python -m py_compile hello.py`, `node --check app.js`, `bash -n x.sh`,
    `python -m pytest` (for .py), `npm test` (for .js).
  * Other files (.txt .html .md .json ...): read_file on that file, and the
    text read back equals what was written. A command that runs something
    on the file and exits 0 also counts (for example
    `python -m json.tool data.json`).
  * The LATEST check wins: if a later check fails, the file is unverified.
  * Writing the file again throws away every earlier check of it.

Things that do NOT count: `cat`, `ls`, `echo`, `python -c "..."`,
`python --version`, anything chained with `;`, `||`, `|` or `&` (those can
hide a failure behind exit code 0), and commands that did not finish.

HONEST LIMITS: this proves a check RAN and PASSED. It cannot prove the
check was a good one. Only files written with write_file are tracked.
Files created by commands are not.

Pure logic, no file or network access. Safe to import anywhere.
"""

import posixpath
import re
import shlex

MAX_BOUNCES = 2

CODE_EXTS = frozenset({".py", ".js", ".mjs", ".sh"})
PY_TEST_MODULES = frozenset({"pytest", "unittest", "compileall"})

_EXIT_CODE = re.compile(r"\[EXIT CODE\] (-?\d+)\s*$")
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PYTHON = re.compile(r"^python[0-9.]*$")


def normalize_path(path):
    """Same spelling for the same file: ./a/../b.txt and b.txt match."""
    text = str(path or "").replace("\\", "/").strip()
    return posixpath.normpath(text) if text else ""


def exit_code(output):
    """The exit code printed at the end of a run_command result, or None."""
    match = _EXIT_CODE.search(output or "")
    return int(match.group(1)) if match else None


def _mentions(args, path):
    """True if one of the arguments names this file (by path or file name)."""
    base = posixpath.basename(path)
    for arg in args:
        if arg.startswith("-"):
            continue
        cleaned = normalize_path(arg)
        if cleaned == path or posixpath.basename(cleaned) == base:
            return True
    return False


def _segment_checks_file(segment, path):
    """Does this ONE simple command actually run or test `path`?"""
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return False
    while tokens and _ENV_ASSIGN.match(tokens[0]):
        tokens.pop(0)
    if not tokens:
        return False

    program = posixpath.basename(tokens[0])
    args = tokens[1:]
    ext = posixpath.splitext(path)[1].lower()

    if _PYTHON.match(program):
        if "-c" in args:
            return False                      # python -c "print('ok')" proves nothing
        if "-m" in args:
            index = args.index("-m")
            module = args[index + 1] if index + 1 < len(args) else ""
            if module in PY_TEST_MODULES:
                return ext == ".py" or _mentions(args, path)
            return _mentions(args, path)      # py_compile x.py, json.tool x.json ...
        return _mentions(args, path)          # python x.py

    if program == "node":
        if "-e" in args or "-p" in args or "--eval" in args or "--print" in args:
            return False
        return _mentions(args, path)          # node x.js, node --check x.js

    if program in ("bash", "sh"):
        if "-c" in args:
            return False
        return _mentions(args, path)          # bash x.sh, bash -n x.sh

    if program in ("pytest", "py.test"):
        return ext == ".py" or _mentions(args, path)

    if program == "npm":
        if args[:1] == ["test"] or args[:2] == ["run", "test"]:
            return ext in (".js", ".mjs")
        return False

    return False


def command_checks_file(command, path):
    """
    True if `command`, finishing with exit code 0, is evidence that `path`
    works. Deliberately strict: anything that could hide a failure is out.
    """
    if not isinstance(command, str) or not command.strip():
        return False
    cleaned = command.replace("2>&1", " ").replace("1>&2", " ")
    pieces = cleaned.split("&&")
    for piece in pieces:
        if re.search(r"[;|&`\n\r]", piece) or "$(" in piece:
            return False
    return any(_segment_checks_file(piece, path) for piece in pieces)


def _how_to_check(path):
    ext = posixpath.splitext(path)[1].lower()
    if ext == ".py":
        return f"run it, for example `python {path}` (must exit with code 0)"
    if ext in (".js", ".mjs"):
        return f"run it, for example `node {path}` (must exit with code 0)"
    if ext == ".sh":
        return f"run it, for example `bash {path}` (must exit with code 0)"
    return "call read_file on it and confirm the content is right"


class VerifyState:
    """One per program run. Call reset() whenever the human types a message."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.files = {}      # path -> {"content", "status", "evidence"}
        self.bounces = 0
        self.errors = 0

    # ------------------------------------------------------------------
    # Watching the tools
    # ------------------------------------------------------------------

    def note_tool(self, name, arguments, output):
        """Call after every tool that actually ran. Never raises."""
        try:
            self._note(name, arguments, output)
        except Exception:
            self.errors += 1

    def _note(self, name, arguments, output):
        if not isinstance(arguments, dict):
            return
        output = output or ""

        if name == "write_file":
            if output.startswith("File written successfully"):
                path = normalize_path(arguments.get("path"))
                if path:
                    self.files[path] = {
                        "content": arguments.get("content", ""),
                        "status": "unchecked",
                        "evidence": "",
                    }
            return

        if name == "read_file":
            path = normalize_path(arguments.get("path"))
            record = self.files.get(path)
            if record is None:
                return
            if output == record["content"]:
                if posixpath.splitext(path)[1].lower() not in CODE_EXTS:
                    record["status"] = "ok"
                    record["evidence"] = "read back, matches what was written"
            else:
                record["status"] = "failed"
                record["evidence"] = "read back does NOT match what was written"
            return

        if name == "run_command":
            code = exit_code(output)
            if code is None:
                return                      # blocked, denied, or timed out: no verdict
            command = arguments.get("command")
            for path, record in self.files.items():
                if command_checks_file(command, path):
                    record["status"] = "ok" if code == 0 else "failed"
                    record["evidence"] = f"{command.strip()} (exit code {code})"

    # ------------------------------------------------------------------
    # Using the result
    # ------------------------------------------------------------------

    def pending(self):
        """Paths written during this request that have no passing check."""
        return {p: r for p, r in self.files.items() if r["status"] != "ok"}

    def check_final(self, answer=""):
        """
        Call when the model wants to give its final answer. Returns None if
        the answer may be shown, otherwise the message to send the model.
        """
        if self.errors or self.bounces >= MAX_BOUNCES or not self.pending():
            return None
        self.bounces += 1

        lines = [
            "VERIFY REQUIRED (message from the program, not the human): you "
            "changed files in this request but no passing check has run on "
            "them since their last change, so you cannot say the work is done yet.",
            "Still unchecked:",
        ]
        for path, record in self.pending().items():
            if record["status"] == "failed":
                lines.append(f"- {path}: the last check FAILED: {record['evidence']}. "
                             "Fix the file, then check it again.")
            else:
                lines.append(f"- {path}: {_how_to_check(path)}")
        lines.append(
            "Do the checks now. If a check fails, fix it and check again. If "
            "you cannot check something (for example the human refused a "
            "command), say exactly that in your answer instead of saying it is done."
        )
        return "\n".join(lines)

    def report(self):
        """
        (all_ok, text) for the human. text is "" when no files were written.
        Written by the program, so the model cannot soften it.
        """
        if not self.files:
            return True, ""

        if self.errors:
            return False, ("[VERIFY] NOT VERIFIED - the verify step hit an internal error. "
                           "Treat the work above as unchecked.")

        pending = self.pending()
        lines = []
        if pending:
            lines.append("[VERIFY] NOT VERIFIED - treat the work above as unchecked:")
            for path, record in pending.items():
                if record["status"] == "failed":
                    lines.append(f"  FAILED  {path}  <- {record['evidence']}")
                else:
                    lines.append(f"  NO CHECK  {path}  <- nothing passed after the last write")
        else:
            lines.append("[VERIFY] Checked after the last change:")

        for path, record in self.files.items():
            if record["status"] == "ok":
                lines.append(f"  OK  {path}  <- {record['evidence']}")

        return (not pending), "\n".join(lines)
