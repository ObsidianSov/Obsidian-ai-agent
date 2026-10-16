"""
Test suite for the Task Engine (M8)

Run directly: python test_task_engine.py

Part 1 tests task_engine.py on its own (pure logic).
Part 2 drives the REAL ai.py tool pipeline (execute_tool) in a throwaway
       folder: the real workspace, memory and logs are never touched.
Part 3 runs the REAL main() chat loop with a scripted fake model and a
       pretend human, to prove the order of work is enforced end to end.

NOT tested here: a real model (OpenRouter) and the model's judgement.
Those need the live check on the phone.
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

from task_engine import (
    ACT,
    INSPECT,
    READ_ONLY_TOOLS,
    TaskState,
    format_plan,
    is_read_only_command,
    parse_do_prefix,
    validate_plan,
)

REPO = Path(__file__).resolve().parent
VALID_KEY = "sk-or-v1-" + "a1" * 32   # right shape, not a real key
results = []


def check(ok, label):
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    results.append(bool(ok))


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


GOOD_PLAN = {"summary": "Add a notes file", "steps": ["Write notes.txt"], "files": ["notes.txt"]}


def asked(answer):
    """An `ask` function that always gives one answer, and records the call."""
    calls = []

    def ask(prompt):
        calls.append(prompt)
        if isinstance(answer, Exception):
            raise answer
        return answer
    ask.calls = calls
    return ask


def part1_pure_logic():
    # ---------- read-only commands: allowed ----------
    read_only = [
        "ls", "ls -la", "cat a.txt", "head -n 5 a.txt", "tail -n 20 a.txt", "wc -l a.txt", "pwd",
        'grep -rn "foo" .', 'grep "a|b" file.txt', 'find . -name "*.py"', "git status",
        "git log --oneline -5", "git diff", "git show HEAD", "git ls-files", "python --version",
        "python3 -V", "node -v", "npm --version", "pip --version", "cat a.txt | head -5",
        "ls | grep py", "ls -la | grep -i test | wc -l", "du -sh .", "stat a.txt", "file a.txt",
        "which python", "ls 2>/dev/null", "ls 2>&1", "ls >/dev/null 2>&1", "git status 2>/dev/null",
    ]
    for command in read_only:
        check(is_read_only_command(command), f"read-only command is allowed in INSPECT: {command}")

    # ---------- everything that can write or run code: not allowed ----------
    not_read_only = [
        "echo hi > a.txt", "cat a > b", "cat a >> b", "ls; rm x", "ls && rm x", "ls &", "ls || rm x",
        "ls $(rm x)", "ls `rm x`", "rm a", "mv a b", "cp a b", "mkdir d", "touch a", "python test.py",
        'python -c "print(1)"', "python --version extra", "node app.js", "npm install", "npm run build",
        "pip install requests", "git commit -m x", "git add .", "git push", "git checkout x",
        "git diff --output=x.txt", "git -c core.pager=sh log", "git branch newbranch", "find . -delete",
        "find . -exec rm {} +", "find . -fprint out.txt", "tail -f log.txt", "sed -i s/a/b/ f",
        "sort -o out in", "/bin/ls", "", "   ", "ls |", "| ls", "ls\nrm x", "curl http://example.com",
        "tee out.txt", "cat a | sh", "ls | python", "(ls)", "ls > out.txt", "ls 2> err.txt", "ls &>/dev/null",
        "ls >& out.txt", "ls 2>&1 > out.txt", "cat <<EOF", "grep 'unclosed file", "bash script.sh",
    ]
    for command in not_read_only:
        check(not is_read_only_command(command), f"not read-only, so locked in INSPECT: {command!r}")
    check(not is_read_only_command(None) and not is_read_only_command(42), "non-string commands are never read-only")

    # ---------- the phase lock ----------
    state = TaskState()
    check(state.phase == INSPECT, "a new request starts in INSPECT")
    for name in sorted(READ_ONLY_TOOLS):
        check(state.check_tool(name, {}) is None, f"INSPECT allows {name}")
    for name in ["write_file", "create_directory", "some_future_tool"]:
        locked = state.check_tool(name, {"path": "x"})
        check(locked is not None and locked.startswith("LOCKED"), f"INSPECT locks {name} (default deny)")
    check(state.check_tool("run_command", {"command": "ls"}) is None, "INSPECT allows run_command ls")
    check(state.check_tool("run_command", {"command": "touch x"}).startswith("LOCKED"), "INSPECT locks run_command touch")
    check(state.check_tool("run_command", {}).startswith("LOCKED") and state.check_tool("run_command", None).startswith("LOCKED"),
          "run_command with missing arguments is locked")
    check("submit_plan" in state.check_tool("write_file", {}), "the locked message tells the model to call submit_plan")

    # ---------- plan validation ----------
    plan, problem = validate_plan(GOOD_PLAN)
    check(problem is None and plan["steps"] == ["Write notes.txt"] and plan["files"] == ["notes.txt"], "a good plan is accepted")
    plan, problem = validate_plan({"summary": "x", "steps": ["a"]})
    check(problem is None and plan["files"] == [], "files are optional")
    bad_plans = {
        "not an object": "do it",
        "no summary": {"steps": ["a"]},
        "blank summary": {"summary": "   ", "steps": ["a"]},
        "no steps": {"summary": "x"},
        "empty steps": {"summary": "x", "steps": []},
        "steps not a list": {"summary": "x", "steps": "do a thing"},
        "empty step": {"summary": "x", "steps": ["a", ""]},
        "step not a string": {"summary": "x", "steps": [1]},
        "too many steps": {"summary": "x", "steps": ["s"] * 16},
        "files not a list": {"summary": "x", "steps": ["a"], "files": "a.txt"},
        "too many files": {"summary": "x", "steps": ["a"], "files": ["f"] * 31},
    }
    for label, bad in bad_plans.items():
        plan, problem = validate_plan(bad)
        check(plan is None and problem, f"invalid plan rejected: {label}")

    # ---------- plan text is safe to print ----------
    plan, _ = validate_plan({"summary": "\x1b[31mRED\x1b[0m goal\x07", "steps": ["step\x1b]0;evil\x07 one"], "files": ["a\x00b"]})
    shown = format_plan(plan)
    check("\x1b" not in shown and "\x07" not in shown and "\x00" not in shown, "escape codes and control characters are removed from a plan")
    check("Goal:" in shown and "1. " in shown and "Files it expects" in shown, "a plan is shown with goal, numbered steps and files")

    # ---------- approval flow ----------
    for answer in ["yes", "y", "YES", "  Yes  ", "Y"]:
        state, shown = TaskState(), []
        ask = asked(answer)
        out = state.submit_plan(GOOD_PLAN, ask, show=shown.append)
        check(state.phase == ACT and out.startswith("PLAN APPROVED") and len(ask.calls) == 1,
              f"{answer!r} approves the plan and unlocks tools")

    state = TaskState()
    state.submit_plan(GOOD_PLAN, asked("yes"), show=lambda *_: None)
    check(all(state.check_tool(n, {"command": "touch x"}) is None for n in ["write_file", "create_directory", "run_command"]),
          "after approval write_file, create_directory and run_command are unlocked")

    for answer in ["no", "n", "NO", "", "   "]:
        state = TaskState()
        out = state.submit_plan(GOOD_PLAN, asked(answer), show=lambda *_: None)
        check(state.phase == INSPECT and state.plan_rejected and out.startswith("LOCKED") and "rejected" in out,
              f"{answer!r} rejects the plan and keeps everything locked")

    state = TaskState()
    state.submit_plan(GOOD_PLAN, asked("no"), show=lambda *_: None)
    ask = asked("yes")
    out = state.submit_plan(GOOD_PLAN, ask, show=lambda *_: None)
    check(ask.calls == [] and state.phase == INSPECT and "rejected" in out, "after a 'no' the model cannot ask again for the same request")
    check("rejected" in state.check_tool("write_file", {}) and state.check_tool("read_file", {}) is None,
          "after a 'no' writes stay locked (with a stop message) but reading still works")

    state = TaskState()
    out = state.submit_plan(GOOD_PLAN, asked(EOFError()), show=lambda *_: None)
    check(state.phase == INSPECT and state.plan_rejected, "no answer available (EOF) counts as a no")

    for answer in ["yes please", "yes, but use React", "sure", "ok", "go ahead", "yes\nno"]:
        state = TaskState()
        out = state.submit_plan(GOOD_PLAN, asked(answer), show=lambda *_: None)
        check(state.phase == INSPECT and not state.plan_rejected and out.startswith("PLAN NOT APPROVED"),
              f"{answer!r} is NOT an approval; it goes back to the model as feedback")

    state = TaskState()
    out = state.submit_plan(GOOD_PLAN, asked("use a smaller file"), show=lambda *_: None)
    check("use a smaller file" in out and state.check_tool("write_file", {}) is not None, "feedback reaches the model and tools stay locked")
    out = state.submit_plan(GOOD_PLAN, asked("yes"), show=lambda *_: None)
    check(state.phase == ACT and out.startswith("PLAN APPROVED"), "after feedback the model can submit a revised plan and be approved")

    state = TaskState()
    ask = asked("yes")
    out = state.submit_plan({"summary": "x"}, ask, show=lambda *_: None)
    check(out.startswith("INVALID PLAN") and ask.calls == [] and state.phase == INSPECT, "an invalid plan is bounced without bothering the human")

    state = TaskState()
    state.reset(start_in_act=True)
    ask = asked("no")
    out = state.submit_plan(GOOD_PLAN, ask, show=lambda *_: None)
    check(out.startswith("No plan needed") and ask.calls == [], "in ACT (e.g. after /do) submit_plan does not ask again")

    state = TaskState()
    state.submit_plan(GOOD_PLAN, asked("yes"), show=lambda *_: None)
    state.reset()
    check(state.phase == INSPECT and state.plan is None and not state.plan_rejected, "a new human message resets to INSPECT")
    state.submit_plan(GOOD_PLAN, asked("no"), show=lambda *_: None)
    state.reset()
    check(state.phase == INSPECT and not state.plan_rejected, "a new human message clears an earlier 'no'")
    state.reset(start_in_act=True)
    check(state.phase == ACT and state.check_tool("write_file", {}) is None, "reset(start_in_act=True) starts unlocked")

    # ---------- /do ----------
    check(parse_do_prefix("/do fix the button") == ("fix the button", True), "/do <text> skips the plan")
    check(parse_do_prefix("  /DO  fix it ") == ("fix it", True), "/do is case-insensitive and ignores spaces")
    check(parse_do_prefix("/do") == ("", True), "/do alone is recognised (the caller shows usage)")
    check(parse_do_prefix("/do line one\nline two") == ("line one\nline two", True), "/do works with a multi-line pasted message")
    for text in ["do fix it", "/dont fix it", "please /do fix it", "/document this", "hello", ""]:
        check(parse_do_prefix(text) == (text, False), f"not a /do command: {text!r}")


# ----------------------------------------------------------------------
# Parts 2 and 3: the real ai.py
# ----------------------------------------------------------------------

def copy_code(dest):
    dest.mkdir(parents=True, exist_ok=True)
    for f in REPO.glob("*.py"):
        if not f.name.startswith("test_"):
            shutil.copy(f, dest / f.name)


def load_ai(folder):
    sys.path.insert(0, str(folder))
    for name in ("ai", "task_engine", "action_gate", "script_gate", "llm_client", "web_tools",
                 "console_input", "memory_system", "audit_log", "killswitch"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("ai_under_test", folder / "ai.py")
    module = importlib.util.module_from_spec(spec)
    os.environ["OPENROUTER_API_KEY"] = VALID_KEY
    spec.loader.exec_module(module)
    return module


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

    def tool_results(self, call_index):
        """Tool-message texts the model saw on its call number `call_index` (0-based)."""
        return [m["content"] for m in self.seen[call_index] if m.get("role") == "tool"]


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


def part2_real_pipeline(ai):
    ws = ai.WORKSPACE
    ai.TASK.reset()

    check(ai.TASK.phase == INSPECT, "ai.py starts every request in INSPECT")

    out = tool(ai, "write_file", {"path": "blocked.txt", "content": "x"})
    check(out.startswith("LOCKED") and not (ws / "blocked.txt").exists(), "write_file is LOCKED in INSPECT and nothing is written")
    out = tool(ai, "create_directory", {"path": "newdir"})
    check(out.startswith("LOCKED") and not (ws / "newdir").exists(), "create_directory is LOCKED in INSPECT")
    out = tool(ai, "run_command", {"command": "touch made.txt"})
    check(out.startswith("LOCKED") and not (ws / "made.txt").exists(), "a writing command is LOCKED in INSPECT and does not run")
    out = tool(ai, "run_command", {"command": "echo hi > made.txt"})
    check(out.startswith("LOCKED") and not (ws / "made.txt").exists(), "a redirect is LOCKED in INSPECT")

    (ws / "existing.txt").write_text("already here")
    check("existing.txt" in tool(ai, "list_files", {"path": "."}), "list_files works in INSPECT")
    check(tool(ai, "read_file", {"path": "existing.txt"}) == "already here", "read_file works in INSPECT")
    check("existing.txt" in tool(ai, "run_command", {"command": "ls"}), "a read-only command (ls) really runs in INSPECT")
    check("already here" in tool(ai, "run_command", {"command": "cat existing.txt | head -5"}), "a read-only pipe really runs in INSPECT")

    entries = ai.audit.read_all()
    locked = [e for e in entries if e.get("tier") == "LOCKED"]
    check(len(locked) >= 4 and all(e["success"] is False for e in locked), "every locked call is written to the audit log as LOCKED / failed")

    # real approval through the real tool
    out = tool(ai, "submit_plan", GOOD_PLAN, human=Human("yes"))
    check(out.startswith("PLAN APPROVED") and ai.TASK.phase == ACT, "submit_plan + 'yes' unlocks the request")
    out = tool(ai, "write_file", {"path": "approved.txt", "content": "ok"})
    check("written" in out.lower() and (ws / "approved.txt").read_text() == "ok", "after approval write_file works")
    check(any(e["tool"] == "submit_plan" and e["tier"] == "PLAN" and e["success"] for e in ai.audit.read_all()),
          "the approved plan is recorded in the audit log")

    out = tool(ai, "run_command", {"command": "rm -rf /"})
    check(out.startswith("BLOCKED"), "after approval the Action Gate still blocks rm -rf /")
    human = Human("no")
    out = tool(ai, "run_command", {"command": "rm approved.txt"}, human=human)
    check(out.startswith("DENIED") and (ws / "approved.txt").exists() and len(human.prompts) == 1,
          "after approval a risky command still needs its own yes (and 'no' keeps the file)")

    ai.TASK.reset()
    out = tool(ai, "submit_plan", GOOD_PLAN, human=Human("no"))
    check(out.startswith("LOCKED") and ai.TASK.phase == INSPECT, "submit_plan + 'no' keeps the lock")
    entries = [e for e in ai.audit.read_all() if e["tool"] == "submit_plan"]
    check(entries[-1]["success"] is False, "a rejected plan is logged as failed")
    out = tool(ai, "write_file", {"path": "after_no.txt", "content": "x"})
    check("rejected" in out and not (ws / "after_no.txt").exists(), "after 'no' writing is refused with a stop message")

    ai.TASK.reset()
    out = tool(ai, "submit_plan", {"summary": "x"}, human=Human("yes"))
    check(out.startswith("INVALID PLAN") and ai.TASK.phase == INSPECT, "an invalid plan through the real tool changes nothing")

    # every tool the model can see has been consciously classified
    ai.TASK.reset()
    names = [t["function"]["name"] for t in ai.TOOLS]
    locked_names = {n for n in names if ai.TASK.check_tool(n, {}) is not None}
    check(locked_names == {"write_file", "create_directory", "run_command"},
          f"only the changing tools are locked in INSPECT (locked: {sorted(locked_names)})")
    check(set(names) - locked_names <= READ_ONLY_TOOLS, "every unlocked tool is on the read-only list (a new tool starts locked)")
    plan_tool = next(t for t in ai.TOOLS if t["function"]["name"] == "submit_plan")["function"]["parameters"]
    check(plan_tool["required"] == ["summary", "steps"] and {"summary", "steps", "files"} <= set(plan_tool["properties"]),
          "the submit_plan tool is offered to the model with summary, steps and files")
    for phrase in ["INSPECT", "submit_plan", "/do", "LOCKED"]:
        check(phrase in ai.SYSTEM_PROMPT, f"the system prompt explains the phases ({phrase})")


def part3_real_loop(folder):
    # --- A: locked first, plan, approve, then it works ---
    ai = load_ai(folder / "a")
    ws = ai.WORKSPACE
    human = Human("yes")
    model, printed = run_main(ai, ["build a notes file", "exit"], [
        calls(tool_call("c1", "write_file", {"path": "notes.txt", "content": "v1"})),
        calls(tool_call("c2", "submit_plan", GOOD_PLAN)),
        calls(tool_call("c3", "write_file", {"path": "notes.txt", "content": "v1"})),
        calls(tool_call("c4", "read_file", {"path": "notes.txt"})),   # M9: check before saying done
        says("done"),
    ], human)
    check(model.tool_results(1)[0].startswith("LOCKED"), "loop: the model's first write attempt is LOCKED")
    check(model.tool_results(2)[1].startswith("PLAN APPROVED"), "loop: the human's yes reaches the model")
    check((ws / "notes.txt").read_text() == "v1", "loop: after the plan is approved the file really gets written")
    check(len(human.prompts) == 1 and "Approve this plan" in human.prompts[0], "loop: the human was asked exactly once")
    check("PLAN FROM OBSIDIAN AI" in printed and "Add a notes file" in printed, "loop: the human sees the plan on screen")
    check("done" in printed, "loop: the final answer is printed")

    # --- B: /do skips the plan, and the model never sees the "/do" ---
    ai = load_ai(folder / "b")
    ws = ai.WORKSPACE
    human = Human()
    model, printed = run_main(ai, ["/do make a file", "exit"], [
        calls(tool_call("c1", "write_file", {"path": "quick.txt", "content": "fast"})),
        calls(tool_call("c2", "read_file", {"path": "quick.txt"})),   # M9: check before saying done
        says("made it"),
    ], human)
    user_msgs = [m["content"] for m in model.seen[0] if m.get("role") == "user"]
    check((ws / "quick.txt").read_text() == "fast" and human.prompts == [], "loop: /do writes right away with no plan prompt")
    check(user_msgs == ["make a file"], "loop: the model receives the request without the /do prefix")
    check("plan step skipped" in printed, "loop: the human is told the plan step was skipped")

    ai = load_ai(folder / "b2")
    model, printed = run_main(ai, ["/do", "exit"], [], Human())
    check("Usage: /do" in printed and model.seen == [], "loop: /do alone shows usage and does not call the model")

    # --- C: the lock comes back with every new message ---
    ai = load_ai(folder / "c")
    ws = ai.WORKSPACE
    human = Human("yes")
    model, printed = run_main(ai, ["first request", "second request", "exit"], [
        calls(tool_call("c1", "submit_plan", GOOD_PLAN)),
        says("first done"),
        calls(tool_call("c2", "write_file", {"path": "second.txt", "content": "x"})),
        says("second done"),
    ], human)
    check(model.tool_results(3)[-1].startswith("LOCKED") and not (ws / "second.txt").exists(),
          "loop: approval does not carry over: the next message starts locked again")

    # --- D: 'no' stops the writing ---
    ai = load_ai(folder / "d")
    ws = ai.WORKSPACE
    human = Human("no")
    model, printed = run_main(ai, ["do it", "exit"], [
        calls(tool_call("c1", "submit_plan", GOOD_PLAN)),
        calls(tool_call("c2", "write_file", {"path": "nope.txt", "content": "x"}),
              tool_call("c3", "submit_plan", GOOD_PLAN)),
        says("ok, waiting for you"),
    ], human)
    results_seen = model.tool_results(2)
    check(not (ws / "nope.txt").exists() and len(human.prompts) == 1, "loop: after 'no' nothing is written and the human is not asked again")
    check("rejected" in results_seen[1] and "rejected" in results_seen[2], "loop: the model is told to stop and wait")

    # --- E: feedback lets the model revise, then approval works ---
    ai = load_ai(folder / "e")
    ws = ai.WORKSPACE
    human = Human("use a shorter file", "yes")
    model, printed = run_main(ai, ["build it", "exit"], [
        calls(tool_call("c1", "submit_plan", GOOD_PLAN)),
        calls(tool_call("c2", "submit_plan", {**GOOD_PLAN, "summary": "Shorter notes file"})),
        calls(tool_call("c3", "write_file", {"path": "notes.txt", "content": "short"})),
        calls(tool_call("c4", "read_file", {"path": "notes.txt"})),   # M9: check before saying done
        says("done"),
    ], human)
    check("use a shorter file" in model.tool_results(1)[0] and model.tool_results(1)[0].startswith("PLAN NOT APPROVED"),
          "loop: the human's feedback is passed to the model")
    check((ws / "notes.txt").read_text() == "short" and len(human.prompts) == 2, "loop: after the revised plan is approved the work is done")

    # --- F: a plain question needs no plan ---
    ai = load_ai(folder / "f")
    human = Human()
    model, printed = run_main(ai, ["what is 2+2", "exit"], [says("4")], human)
    check(human.prompts == [] and "4" in printed and "LOCKED" not in printed, "loop: a question is answered with no plan and no lock")

    # --- G: read-only inspection first, then plan, then act (the intended order) ---
    ai = load_ai(folder / "g")
    ws = ai.WORKSPACE
    (ws / "old.txt").write_text("legacy")
    human = Human("yes")
    model, printed = run_main(ai, ["extend the old file", "exit"], [
        calls(tool_call("c1", "list_files", {"path": "."}), tool_call("c2", "read_file", {"path": "old.txt"})),
        calls(tool_call("c3", "submit_plan", {"summary": "Extend old.txt", "steps": ["Append a line"], "files": ["old.txt"]})),
        calls(tool_call("c4", "write_file", {"path": "old.txt", "content": "legacy+new"})),
        calls(tool_call("c5", "read_file", {"path": "old.txt"})),   # M9: check before saying done
        says("extended"),
    ], human)
    check("old.txt" in model.tool_results(1)[0] and model.tool_results(1)[1] == "legacy" and "LOCKED" not in "".join(model.tool_results(1)),
          "loop: inspecting first works without any prompt")
    check((ws / "old.txt").read_text() == "legacy+new", "loop: inspect -> plan -> approve -> act works in order")


def run_all_tests():
    part1_pure_logic()

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        copy_code(folder / "pipeline")
        part2_real_pipeline(load_ai(folder / "pipeline"))
        for name in "a b b2 c d e f g".split():
            copy_code(folder / name)
        part3_real_loop(folder)

    passed, total = sum(results), len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")
    print("[SUCCESS] Task Engine verified." if passed == total else "[FAILURE] Some tests failed — review above.")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
