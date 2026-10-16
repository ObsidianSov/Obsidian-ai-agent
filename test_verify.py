"""
Test suite for the Verify step (M9)

Run directly: python test_verify.py

Part 1 tests verify.py on its own (pure logic): what counts as a check and
       what does not, including checks a model could use to fake "it works".
Part 2 drives the REAL ai.py tool pipeline (execute_tool) in a throwaway
       folder, with real files and real commands. The real workspace,
       memory and logs are never touched.
Part 3 runs the REAL main() chat loop with a scripted fake model and a
       pretend human, to prove "done" is held back until a check passes.

NOT tested here: a real model (OpenRouter) and whether a real model will
choose a good check. A check that RAN and PASSED is all this can prove.
"""

import builtins
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from verify import (
    MAX_BOUNCES,
    VerifyState,
    command_checks_file,
    exit_code,
    normalize_path,
)

REPO = Path(__file__).resolve().parent
VALID_KEY = "sk-or-v1-" + "a1" * 32   # right shape, not a real key
PY = Path(sys.executable).name        # python or python3, whatever runs this test
results = []


def check(ok, label):
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    results.append(bool(ok))


# ----------------------------------------------------------------------
# Part 1: pure logic
# ----------------------------------------------------------------------

WROTE = "File written successfully: x"
OK_EXIT = "hello\n[EXIT CODE] 0"
BAD_EXIT = "boom\n[STDERR]\nTraceback...\n[EXIT CODE] 1"


def part1_pure_logic():
    # --- small helpers ---
    check(normalize_path("./a/../b.txt") == "b.txt", "normalize_path: ./a/../b.txt is b.txt")
    check(normalize_path("sub\\x.py") == "sub/x.py", "normalize_path: backslashes become slashes")
    check(normalize_path(None) == "" and normalize_path("") == "", "normalize_path: empty input gives empty text")
    check(exit_code("out\n[EXIT CODE] 0") == 0, "exit_code: reads 0")
    check(exit_code("out\n[EXIT CODE] 2") == 2, "exit_code: reads 2")
    check(exit_code("Command timed out after 120 seconds.") is None, "exit_code: a timeout has no exit code")
    check(exit_code("BLOCKED: nope") is None and exit_code("") is None and exit_code(None) is None,
          "exit_code: blocked, empty and None have no exit code")
    check(exit_code("[EXIT CODE] 0 and then more text") is None,
          "exit_code: only counts when it is the LAST thing printed")

    # --- commands that DO check a file ---
    good = [
        ("python hello.py", "hello.py"),
        ("python3 hello.py", "hello.py"),
        ("python3.12 hello.py", "hello.py"),
        ("python hello.py 2>&1", "hello.py"),
        ("FOO=1 python hello.py", "hello.py"),
        ("python -m py_compile hello.py", "hello.py"),
        ("python -m pytest", "hello.py"),
        ("python -m unittest", "hello.py"),
        ("python -m compileall .", "hello.py"),
        ("pytest", "hello.py"),
        ("pytest -q tests", "hello.py"),
        ("cd sub && python x.py", "sub/x.py"),
        ("python sub/x.py", "sub/x.py"),
        ("ls && python hello.py", "hello.py"),
        ("python hello.py && echo done", "hello.py"),
        ("node app.js", "app.js"),
        ("node --check app.js", "app.js"),
        ("npm test", "app.js"),
        ("npm run test", "app.js"),
        ("bash -n run.sh", "run.sh"),
        ("sh run.sh", "run.sh"),
        ("python -m json.tool data.json", "data.json"),
    ]
    for command, path in good:
        check(command_checks_file(command, path) is True, f"counts as a check of {path}: {command}")

    # --- commands that look like checks but are NOT ---
    bad = [
        ("python -c \"print('hello.py')\"", "hello.py"),
        ("python3 -c 'import hello'", "hello.py"),
        ("echo hello.py", "hello.py"),
        ("cat hello.py", "hello.py"),
        ("ls hello.py", "hello.py"),
        ("head hello.py", "hello.py"),
        ("python --version", "hello.py"),
        ("python other.py", "hello.py"),
        ("python hello.py || true", "hello.py"),
        ("python hello.py; true", "hello.py"),
        ("python hello.py | tail -1", "hello.py"),
        ("python hello.py &", "hello.py"),
        ("python hello.py & wait", "hello.py"),
        ("(python hello.py; true)", "hello.py"),
        ("python hello.py $(true)", "hello.py"),
        ("python `echo hello.py`", "hello.py"),
        ("python hello.py\ntrue", "hello.py"),
        ("python -m http.server", "hello.py"),
        ("python -m pytest", "index.html"),      # a test run does not verify an html file
        ("npm test", "hello.py"),                # npm test does not verify a python file
        ("npm install", "app.js"),
        ("node -e \"1\"", "app.js"),
        ("python -c \"print(1)\" hello.py", "hello.py"),   # the file name is only an argument to the -c code
        ("node -e \"1\" app.js", "app.js"),
        ("bash -c 'true' run.sh", "run.sh"),
        ("node -p 1", "app.js"),
        ("bash -c 'run.sh'", "run.sh"),
        ("curl http://x/hello.py", "hello.py"),
        ("python 'hello.py", "hello.py"),        # unbalanced quote: cannot be parsed
        ("", "hello.py"),
        ("   ", "hello.py"),
        (None, "hello.py"),
        (["python", "hello.py"], "hello.py"),
    ]
    for command, path in bad:
        check(command_checks_file(command, path) is False, f"does NOT count as a check of {path}: {command!r}")

    # --- a plain text file: read-back must match what was written ---
    v = VerifyState()
    check(v.check_final("done") is None and v.report() == (True, ""), "nothing written: no bounce and no report")
    v.note_tool("write_file", {"path": "notes.txt", "content": "hello"}, WROTE)
    check(list(v.pending()) == ["notes.txt"], "a successful write puts the file on the unchecked list")
    v.note_tool("read_file", {"path": "notes.txt"}, "hello")
    check(v.pending() == {}, "reading it back with the same text verifies a .txt file")
    check(v.report()[0] is True and "OK  notes.txt" in v.report()[1] and "Checked after the last change" in v.report()[1],
          "the report shows OK and why")

    v = VerifyState()
    v.note_tool("write_file", {"path": "notes.txt", "content": "hello"}, WROTE)
    v.note_tool("read_file", {"path": "notes.txt"}, "something else")
    check(v.files["notes.txt"]["status"] == "failed", "a read-back that does not match is a FAILED check")
    check("does NOT match" in v.files["notes.txt"]["evidence"], "the failure says the read-back did not match")
    check("FAILED" in v.check_final("done"), "the bounce message says the last check FAILED")

    v = VerifyState()
    v.note_tool("write_file", {"path": "notes.txt", "content": "x"}, "Error: could not write")
    v.note_tool("write_file", {"path": "notes.txt", "content": "x"}, "LOCKED: Nothing was changed.")
    check(v.files == {} and v.check_final("done") is None, "a write that did not succeed is not tracked")

    v = VerifyState()
    v.note_tool("write_file", {"path": "./notes.txt", "content": "a"}, WROTE)
    v.note_tool("read_file", {"path": "notes.txt"}, "a")
    check(v.pending() == {}, "./notes.txt and notes.txt are the same file")

    v = VerifyState()
    v.note_tool("write_file", {"path": "a.txt", "content": "a"}, WROTE)
    v.note_tool("read_file", {"path": "other.txt"}, "a")
    check(list(v.pending()) == ["a.txt"], "reading some OTHER file verifies nothing")

    # --- a code file: reading it back is NOT enough ---
    v = VerifyState()
    v.note_tool("write_file", {"path": "hello.py", "content": "print('hi')"}, WROTE)
    v.note_tool("read_file", {"path": "hello.py"}, "print('hi')")
    check(list(v.pending()) == ["hello.py"], "reading a .py file back does NOT verify it")
    v.note_tool("run_command", {"command": "python hello.py"}, "hi\n[EXIT CODE] 0")
    check(v.pending() == {} and "python hello.py (exit code 0)" in v.report()[1],
          "running it with exit code 0 verifies it, and the report names the command")

    v = VerifyState()
    v.note_tool("write_file", {"path": "hello.py", "content": "raise SystemExit(1)"}, WROTE)
    v.note_tool("run_command", {"command": "python hello.py"}, BAD_EXIT)
    check(v.files["hello.py"]["status"] == "failed", "exit code 1 is a FAILED check")
    check(v.report()[0] is False and "FAILED  hello.py" in v.report()[1], "the report shows FAILED for it")

    # --- checks with no verdict ---
    v = VerifyState()
    v.note_tool("write_file", {"path": "hello.py", "content": "x"}, WROTE)
    for output in ["Command timed out after 120 seconds.", "BLOCKED: no", "DENIED: no", "SCRIPT NOT APPROVED", ""]:
        v.note_tool("run_command", {"command": "python hello.py"}, output)
    check(v.files["hello.py"]["status"] == "unchecked", "timed out / blocked / denied commands give no verdict")

    v = VerifyState()
    v.note_tool("write_file", {"path": "hello.py", "content": "x"}, WROTE)
    for command in ["echo hello.py", "cat hello.py", "python -c \"print(1)\"", "python --version", "python hello.py || true"]:
        v.note_tool("run_command", {"command": command}, OK_EXIT)
    check(v.files["hello.py"]["status"] == "unchecked", "fake checks that exit 0 do not verify the file")

    # --- order matters ---
    v = VerifyState()
    v.note_tool("write_file", {"path": "hello.py", "content": "v1"}, WROTE)
    v.note_tool("run_command", {"command": "python hello.py"}, OK_EXIT)
    check(v.pending() == {}, "v1 checked")
    v.note_tool("write_file", {"path": "hello.py", "content": "v2"}, WROTE)
    check(list(v.pending()) == ["hello.py"], "writing it again throws the earlier check away")

    v = VerifyState()
    v.note_tool("write_file", {"path": "hello.py", "content": "v1"}, WROTE)
    v.note_tool("run_command", {"command": "python hello.py"}, OK_EXIT)
    v.note_tool("run_command", {"command": "python hello.py"}, BAD_EXIT)
    check(v.files["hello.py"]["status"] == "failed", "the LATEST check wins: a pass then a fail is a fail")
    v.note_tool("run_command", {"command": "python hello.py"}, OK_EXIT)
    check(v.pending() == {}, "...and a later pass fixes it")

    # --- several files: every one needs its own check ---
    v = VerifyState()
    v.note_tool("write_file", {"path": "a.txt", "content": "a"}, WROTE)
    v.note_tool("write_file", {"path": "b.txt", "content": "b"}, WROTE)
    v.note_tool("write_file", {"path": "app.py", "content": "c"}, WROTE)
    v.note_tool("read_file", {"path": "a.txt"}, "a")
    check(sorted(v.pending()) == ["app.py", "b.txt"], "checking one file does not verify the others")
    v.note_tool("run_command", {"command": "python -m pytest"}, OK_EXIT)
    check(sorted(v.pending()) == ["b.txt"], "a test run verifies .py files only, not .txt files")

    # --- bounce rules ---
    v = VerifyState()
    v.note_tool("write_file", {"path": "hello.py", "content": "x"}, WROTE)
    first = v.check_final("done")
    check(first and first.startswith("VERIFY REQUIRED") and "hello.py" in first and "python hello.py" in first,
          "the bounce message names the file and says how to check it")
    v2 = VerifyState()
    v2.note_tool("write_file", {"path": "n.txt", "content": "x"}, WROTE)
    check("read_file" in v2.check_final("done"), "for a text file the message says to call read_file")
    check(v.check_final("done") is not None, "second bounce happens")
    check(MAX_BOUNCES == 2 and v.check_final("done") is None, "after MAX_BOUNCES (2) the answer is let through")
    ok, text = v.report()
    check(ok is False and "NOT VERIFIED" in text and "NO CHECK  hello.py" in text,
          "...with a program-written NOT VERIFIED notice")
    v.reset()
    check(v.files == {} and v.bounces == 0 and v.report() == (True, ""), "reset() clears everything for the next request")

    # --- it never crashes the agent ---
    v = VerifyState()
    for name, args, out in [("write_file", None, None), ("write_file", [], "x"), ("write_file", {}, WROTE),
                            ("read_file", "x", "y"), ("run_command", {"command": None}, OK_EXIT),
                            ("run_command", {}, OK_EXIT), ("whatever", {"a": 1}, None), ("run_command", 5, 5)]:
        v.note_tool(name, args, out)
    check(v.errors == 0 and v.files == {}, "garbage input is ignored without errors")
    v.files["a"] = "not a record"
    v.note_tool("read_file", {"path": "a"}, "text")
    check(v.errors == 1, "an internal error is counted, not raised")
    check(v.check_final("done") is None, "after an internal error the program does not trap the agent in a loop")
    check("internal error" in v.report()[1] and v.report()[0] is False, "...and the report says it could not verify")


# ----------------------------------------------------------------------
# Parts 2 and 3: the real ai.py
# ----------------------------------------------------------------------

def copy_code(dest):
    dest.mkdir(parents=True, exist_ok=True)
    for f in REPO.glob("*.py"):
        if not f.name.startswith("test_"):
            shutil.copy(f, dest / f.name)


def load_ai(folder):
    copy_code(folder)
    sys.path.insert(0, str(folder))
    for name in ("ai", "task_engine", "verify", "action_gate", "script_gate", "llm_client", "web_tools",
                 "console_input", "memory_system", "audit_log", "killswitch"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("ai_under_test", folder / "ai.py")
    module = importlib.util.module_from_spec(spec)
    os.environ["OPENROUTER_API_KEY"] = VALID_KEY
    spec.loader.exec_module(module)
    return module


class Human:
    """Pretend person answering input() prompts; records what was asked."""
    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)


def tool(ai, name, args, human=None):
    old_input = builtins.input
    if human is not None:
        builtins.input = human
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink):
            return ai.execute_tool(name, args)
    finally:
        builtins.input = old_input


def tool_call(call_id, name, args):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def calls(*tool_calls):
    return {"role": "assistant", "content": None, "tool_calls": list(tool_calls)}


def says(text):
    return {"role": "assistant", "content": text}


class ScriptedModel:
    """Stands in for ask_model: returns pre-written replies and records what it was shown."""
    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []

    def __call__(self, messages):
        self.seen.append([dict(m) for m in messages])
        return {"choices": [{"message": self.replies.pop(0)}]}

    def user_messages_seen_last(self):
        return [m["content"] for m in self.seen[-1] if m.get("role") == "user"]


def run_main(ai, inputs, replies, human):
    """Run the real chat loop. Returns (model, printed_text)."""
    model = ScriptedModel(*replies)
    feed = iter(inputs)
    ai.ask_model = model
    ai.read_message = lambda prompt="": next(feed)
    ai.API_KEY = VALID_KEY
    old_input, sink = builtins.input, io.StringIO()
    builtins.input = human
    try:
        with contextlib.redirect_stdout(sink):
            ai.main()
    finally:
        builtins.input = old_input
    return model, sink.getvalue()


def verify_entries(ai):
    return [e for e in ai.audit.read_all() if e["tool"] == "verify"]


def write(call_id, path, content):
    return tool_call(call_id, "write_file", {"path": path, "content": content})


def read(call_id, path):
    return tool_call(call_id, "read_file", {"path": path})


def run(call_id, command):
    return tool_call(call_id, "run_command", {"command": command})


def part2_real_pipeline(folder):
    ai = load_ai(folder / "p2")
    ws = ai.WORKSPACE

    # A locked write changes nothing and is not tracked.
    ai.TASK.reset()
    ai.VERIFY.reset()
    out = tool(ai, "write_file", {"path": "locked.txt", "content": "x"})
    check(out.startswith("LOCKED") and ai.VERIFY.files == {}, "real pipeline: a LOCKED write is not tracked")

    # A real write is tracked, then verified by a real read-back.
    ai.TASK.reset(start_in_act=True)
    ai.VERIFY.reset()
    tool(ai, "write_file", {"path": "notes.txt", "content": "hello"})
    check(list(ai.VERIFY.pending()) == ["notes.txt"], "real pipeline: a real write goes on the unchecked list")
    tool(ai, "read_file", {"path": "notes.txt"})
    check(ai.VERIFY.pending() == {}, "real pipeline: a real read-back verifies a text file")

    # A real script: run it for real, exit code 0 verifies.
    ai.VERIFY.reset()
    tool(ai, "write_file", {"path": "hello.py", "content": "print('hi')\n"})
    out = tool(ai, "run_command", {"command": f"{PY} hello.py"}, Human("yes"))
    check("hi" in out and "[EXIT CODE] 0" in out, "real pipeline: the script really ran (approved at the script gate)")
    check(ai.VERIFY.pending() == {}, "real pipeline: its real exit code 0 verifies the file")

    # A real failing script: exit code 1 means FAILED.
    ai.VERIFY.reset()
    tool(ai, "write_file", {"path": "bad.py", "content": "raise SystemExit(3)\n"})
    out = tool(ai, "run_command", {"command": f"{PY} bad.py"}, Human("yes"))
    check("[EXIT CODE] 3" in out and ai.VERIFY.files["bad.py"]["status"] == "failed",
          "real pipeline: a real failing script is recorded as FAILED")

    # A script the human refuses never ran, so nothing is verified.
    ai.VERIFY.reset()
    tool(ai, "write_file", {"path": "refused.py", "content": "print('x')\n"})
    out = tool(ai, "run_command", {"command": f"{PY} refused.py"}, Human("no"))
    check("[EXIT CODE]" not in out and ai.VERIFY.files["refused.py"]["status"] == "unchecked",
          "real pipeline: a script the human refused gives no verdict")

    # A read-only command never verifies code.
    ai.VERIFY.reset()
    tool(ai, "write_file", {"path": "c.py", "content": "print(1)\n"})
    tool(ai, "run_command", {"command": "cat c.py"})
    check(list(ai.VERIFY.pending()) == ["c.py"], "real pipeline: cat on a .py file does not verify it")


def part3_real_loop(folder):
    # --- A: "done" is held back until the file is checked ---
    ai = load_ai(folder / "a")
    human = Human()
    model, printed = run_main(ai, ["/do make notes", "exit"], [
        calls(write("c1", "notes.txt", "hello")),
        says("All done!"),
        calls(read("c2", "notes.txt")),
        says("Verified, finished."),
    ], human)
    bounce_texts = [t for t in model.user_messages_seen_last() if t.startswith("VERIFY REQUIRED")]
    check(len(bounce_texts) == 1 and "notes.txt" in bounce_texts[0], "loop A: the model was sent back with a VERIFY REQUIRED message naming the file")
    check("All done!" not in printed, "loop A: the premature 'All done!' was never shown to the human")
    check("Verified, finished." in printed, "loop A: the answer after the check is shown")
    check("Files were changed but not checked yet" in printed, "loop A: the human sees why the answer was held back")
    check("[VERIFY] Checked after the last change:" in printed and "OK  notes.txt" in printed,
          "loop A: the human sees a program-written OK line for the file")
    entries = verify_entries(ai)
    check(len(entries) == 2 and entries[0]["success"] is False and entries[1]["success"] is True and all(e["tier"] == "VERIFY" for e in entries),
          "loop A: the audit log records the bounce (failed) and the final result (ok)")

    # --- B: a .py file needs a RUN, a read-back is not enough ---
    ai = load_ai(folder / "b")
    human = Human("yes", "yes")
    model, printed = run_main(ai, ["/do make a script", "exit"], [
        calls(write("c1", "hello.py", "print('hi')\n")),
        says("first claim"),
        calls(read("c2", "hello.py")),
        says("second claim"),
        calls(run("c3", f"{PY} hello.py")),
        says("third claim, really checked"),
    ], human)
    check("first claim" not in printed and "second claim" not in printed, "loop B: both premature claims were held back")
    check("third claim, really checked" in printed, "loop B: the answer after a real run is shown")
    check(f"OK  hello.py  <- {PY} hello.py (exit code 0)" in printed, "loop B: the OK line names the command that passed")
    check("NOT VERIFIED" not in printed, "loop B: no NOT VERIFIED notice when it really passed")

    # --- C: a failing check, then a fix, then a pass ---
    ai = load_ai(folder / "c")
    human = Human("yes", "yes")
    model, printed = run_main(ai, ["/do make a script", "exit"], [
        calls(write("c1", "app.py", "raise SystemExit(1)\n")),
        calls(run("c2", f"{PY} app.py")),
        says("looks good"),
        calls(write("c3", "app.py", "print('fixed')\n")),
        calls(run("c4", f"{PY} app.py")),
        says("fixed it"),
    ], human)
    bounce_texts = [t for t in model.user_messages_seen_last() if t.startswith("VERIFY REQUIRED")]
    check(len(bounce_texts) == 1 and "FAILED" in bounce_texts[0] and "exit code 1" in bounce_texts[0],
          "loop C: the bounce message says the last check FAILED with exit code 1")
    check("looks good" not in printed and "fixed it" in printed, "loop C: 'looks good' after a failing check is held back")
    check("exit code 0" in printed and "exit code 1" not in printed.split("[VERIFY] Checked")[-1],
          "loop C: the final report shows the passing check, not the old failure")

    # --- D: the model never checks: after 2 bounces the human gets a NOT VERIFIED notice ---
    ai = load_ai(folder / "d")
    human = Human()
    model, printed = run_main(ai, ["/do make notes", "exit"], [
        calls(write("c1", "notes.txt", "hello")),
        says("claim one"),
        says("claim two"),
        says("claim three"),
    ], human)
    check(printed.count("sending the agent back to check them") == 2, "loop D: the model was sent back exactly twice")
    check("claim one" not in printed and "claim two" not in printed and "claim three" in printed,
          "loop D: the third answer is finally shown")
    check("[VERIFY] NOT VERIFIED" in printed and "NO CHECK  notes.txt" in printed,
          "loop D: the notice says NOT VERIFIED and names the file")
    check(printed.index("claim three") < printed.index("NOT VERIFIED"), "loop D: the notice comes after the model's answer, so it can't be buried")
    entries = verify_entries(ai)
    check(len(entries) == 3 and entries[-1]["success"] is False, "loop D: the audit log records the failed result")

    # --- E: fake checks do not pass the gate ---
    ai = load_ai(folder / "e")
    human = Human("yes", "yes")
    model, printed = run_main(ai, ["/do make a script", "exit"], [
        calls(write("c1", "hello.py", "print('hi')\n")),
        calls(run("c2", "echo hello.py"), run("c3", f"{PY} -c \"print(1)\""), run("c4", f"{PY} --version"),
              run("c5", f"{PY} hello.py || true")),
        says("works"),
        says("works for sure"),
        says("works, trust me"),
    ], human)
    check("[VERIFY] NOT VERIFIED" in printed and "works, trust me" in printed and "works for sure" not in printed,
          "loop E: four fake checks that all exit 0 did not get 'works' past the gate")

    # --- F: no files written = no bounce and no report ---
    ai = load_ai(folder / "f")
    human = Human()
    model, printed = run_main(ai, ["what is 2+2", "exit"], [says("4")], human)
    check("4" in printed and "[VERIFY]" not in printed and verify_entries(ai) == [],
          "loop F: a plain question is answered with no verify step")

    # --- G: the normal plan flow is still verified after approval ---
    ai = load_ai(folder / "g")
    human = Human("yes")
    plan = {"summary": "Add notes", "steps": ["Write notes.txt"], "files": ["notes.txt"]}
    model, printed = run_main(ai, ["add notes", "exit"], [
        calls(tool_call("c1", "submit_plan", plan)),
        calls(write("c2", "notes.txt", "v1")),
        says("done after plan"),
        calls(read("c3", "notes.txt")),
        says("really done"),
    ], human)
    check("done after plan" not in printed and "really done" in printed and "OK  notes.txt" in printed,
          "loop G: after plan approval the work is still held until checked")

    # --- H: a rewrite throws the earlier check away ---
    ai = load_ai(folder / "h")
    human = Human()
    model, printed = run_main(ai, ["/do edit twice", "exit"], [
        calls(write("c1", "notes.txt", "v1")),
        calls(read("c2", "notes.txt")),
        calls(write("c3", "notes.txt", "v2")),
        says("v2 written"),
        calls(read("c4", "notes.txt")),
        says("v2 checked"),
    ], human)
    check("v2 written" not in printed and "v2 checked" in printed,
          "loop H: checking v1 does not let a later unchecked v2 through")

    # --- I: the next human message starts clean ---
    ai = load_ai(folder / "i")
    human = Human()
    model, printed = run_main(ai, ["/do make notes", "what is 1+1", "exit"], [
        calls(write("c1", "notes.txt", "v1")),
        calls(read("c2", "notes.txt")),
        says("made"),
        says("2"),
    ], human)
    after_second = printed.split("what is")[-1]
    check(printed.count("[VERIFY] Checked after the last change:") == 1, "loop I: the second message (a question) adds no verify report")
    check(ai.VERIFY.files == {} and ai.VERIFY.bounces == 0, "loop I: the state was reset by the new message")

    # --- J: hitting the safety limit with unchecked work still shows NOT VERIFIED ---
    ai = load_ai(folder / "j")
    human = Human()
    replies = [calls(write("c0", "notes.txt", "v1"))]
    replies += [calls(tool_call(f"l{i}", "list_files", {"path": "."})) for i in range(14)]
    model, printed = run_main(ai, ["/do loop forever", "exit"], replies, human)
    check("[STOPPED]" in printed and "[VERIFY] NOT VERIFIED" in printed,
          "loop J: the 15-round safety stop also shows the NOT VERIFIED notice")


def part4_source_and_prompt():
    source = (REPO / "ai.py").read_text(encoding="utf-8")
    check("from verify import VerifyState" in source, "ai.py imports VerifyState")
    check("VERIFY = VerifyState()" in source, "ai.py creates the VERIFY state")
    check("VERIFY.reset()" in source and "VERIFY.check_final(" in source and "VERIFY.note_tool(" in source,
          "ai.py resets, watches tools and gates the final answer")
    check("VERIFY BEFORE YOU SAY DONE" in source and "NOT VERIFIED" in source,
          "the system prompt tells the model about the verify rule")
    check(source.index("VERIFY.note_tool(") < source.index("tier=tier"),
          "note_tool runs before the audit record in execute_tool")


def run_all_tests():
    part1_pure_logic()

    folder = Path(tempfile.mkdtemp(prefix="verify_test_"))
    old_path = list(sys.path)
    old_key = os.environ.get("OPENROUTER_API_KEY")
    try:
        part2_real_pipeline(folder)
        part3_real_loop(folder)
    finally:
        sys.path[:] = old_path
        if old_key is None:
            os.environ.pop("OPENROUTER_API_KEY", None)
        else:
            os.environ["OPENROUTER_API_KEY"] = old_key
        shutil.rmtree(folder, ignore_errors=True)

    part4_source_and_prompt()

    passed = sum(results)
    total = len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
