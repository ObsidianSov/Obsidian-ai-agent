"""
Test suite for script_gate.py (M6)

Run directly: python test_script_gate.py
Uses a throwaway temp folder as the "workspace". No network.

ai.py starts its chat loop the moment it is imported, so it can't be
loaded in a test. Instead the last tests (1) read ai.py's source and
check the gate call is wired in before the command runs, and (2) lift
the real gated_run_command function out of ai.py and run it with the
command runner and the prompt faked. The real end-to-end check (model +
terminal) is the manual run on the phone.
"""

import ast
import os
import sys
import tempfile
from pathlib import Path

import script_gate as sg
from script_gate import (
    extract_script_targets, find_scripts_needing_approval, review_command,
    fingerprint_script,
)

results = []


def check(ok, label):
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    results.append(bool(ok))


def files_of(cmd):
    targets, _ = extract_script_targets(cmd)
    return [v for _, v in targets]


class Asker:
    """Fake input(): returns scripted answers, records how often asked."""
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def __call__(self, prompt):
        self.calls += 1
        if not self.answers:
            raise EOFError
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a


def quiet(*a, **k):
    pass


def run_all_tests():
    # ---------------- parsing ----------------
    parse_cases = [
        ("python hello.py", ["hello.py"]),
        ("python3 sub/x.py arg1 arg2", ["sub/x.py"]),
        ("/usr/bin/python3 -u x.py", ["x.py"]),
        ("py -3 x.py", ["x.py"]),
        ("python -W ignore x.py", ["x.py"]),
        ("node script.js", ["script.js"]),
        ("bash run.sh", ["run.sh"]),
        ("sh ./run.sh", ["./run.sh"]),
        ("perl a.pl", ["a.pl"]),
        ("ruby a.rb", ["a.rb"]),
        ("./run.sh", ["./run.sh"]),
        ("../run.sh", ["../run.sh"]),
        ("source env.sh", ["env.sh"]),
        (". env.sh", ["env.sh"]),
        ("python 'my script.py'", ["my script.py"]),
        ("sudo python a.py", ["a.py"]),
        ("timeout 10 python a.py", ["a.py"]),
        ("nohup python a.py &", ["a.py"]),
        ("VAR=1 python a.py", ["a.py"]),
        ("time python a.py", ["a.py"]),
        ("nice -n 5 python a.py", ["a.py"]),
        ("echo hi; python a.py; node b.js | cat", ["a.py", "b.js"]),
        ("make && python a.py || bash b.sh", ["a.py", "b.sh"]),
        ("sh -c 'python evil.py'", ["evil.py"]),
        ("bash -c \"bash -c 'python deep.py'\"", ["deep.py"]),
        ("find . -name x -exec python a.py {} \\;", ["a.py"]),
        ("xargs python a.py", ["a.py"]),
        ("python < a.py", ["a.py"]),
        ("python -m mymod", ["mymod"]),
        ("python $FILE", ["$FILE"]),
        ("python script.py 2>&1", ["script.py"]),
        ("python script.py > out.txt", ["script.py"]),
        ("python 2>/dev/null script.py", ["script.py"]),
        ("python -W ignore script.py 2>/dev/null", ["script.py"]),
        ("bash run.sh &> log.txt", ["run.sh"]),
        ("node app.js >> log", ["app.js"]),
        ("python -v script.py", ["script.py"]),
    ]
    for cmd, expected in parse_cases:
        got = files_of(cmd)
        check(got == expected, f"parses {cmd!r} -> {got}")

    for cmd in ["ls -la", "git status", "pip install requests", "echo hi",
                "python --version", "python", 'echo "python evil.py"',
                "cat a.py", "grep python notes.txt", "pip install python-dateutil",
                # the exact command that wrongly triggered a prompt on the phone:
                "python --version && pip --version && node --version 2>/dev/null; npm --version 2>/dev/null",
                "python3 -V", "node -v", "python --help", "bash --version"]:
        t, n = extract_script_targets(cmd)
        check(t == [] and n == [], f"no script found in {cmd!r}")

    for cmd in ["python - <<EOF\nprint(1)\nEOF", "python <<EOF\nprint(1)\nEOF"]:
        t, n = extract_script_targets(cmd)
        check(n == [sg.STDIN_NOTE], f"flags stdin/heredoc script {cmd.splitlines()[0]!r}")

    # ---------------- decisions on real files ----------------
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp).resolve() / "workspace"
        ws.mkdir()
        outside = Path(tmp).resolve() / "outside.py"
        outside.write_text("print('outside')\n")
        (ws / "hello.py").write_text("print('hi')\n")
        (ws / "helper.py").write_text("X = 1\n")
        (ws / "sub").mkdir()
        (ws / "sub" / "a.py").write_text("print('sub a')\n")
        (ws / "mymod.py").write_text("print('mod')\n")
        approved = set()

        # not yet approved -> asked, yes -> remembered
        items = find_scripts_needing_approval("python hello.py", ws, approved)
        check(len(items) == 1 and items[0]["fingerprint"] and "hello.py" in items[0]["display"],
              "unapproved existing script needs approval and shows its name")
        check("print('hi')" in items[0]["preview"], "approval prompt shows the code")

        ask = Asker("yes")
        res = review_command("python hello.py", ws, approved, ask=ask, out=quiet)
        check(res is None and ask.calls == 1 and len(approved) == 1, "yes -> allowed and remembered")

        ask = Asker()
        res = review_command("python hello.py", ws, approved, ask=ask, out=quiet)
        check(res is None and ask.calls == 0, "same content again -> not asked again")

        # content change invalidates
        (ws / "hello.py").write_text("print('changed')\n")
        ask = Asker("no")
        res = review_command("python hello.py", ws, approved, ask=ask, out=quiet)
        check(res and res.startswith("DENIED:") and ask.calls == 1, "edited script -> asked again, 'no' -> DENIED")
        check(len(approved) == 1, "denied script is not added to approvals")

        Asker_ = Asker("y")
        review_command("python hello.py", ws, approved, ask=Asker_, out=quiet)
        ask = Asker()
        res = review_command("python hello.py", ws, approved, ask=ask, out=quiet)
        check(res is None and ask.calls == 0, "'y' also approves and is remembered")

        # sibling change invalidates (hello.py may import helper.py)
        (ws / "helper.py").write_text("X = 2  # edited\n")
        ask = Asker("no")
        review_command("python hello.py", ws, approved, ask=ask, out=quiet)
        check(ask.calls == 1, "changing another .py in the same folder re-asks")

        # a different folder's file is a different approval
        ask = Asker("yes")
        review_command("python sub/a.py", ws, approved, ask=ask, out=quiet)
        check(ask.calls == 1, "a different script needs its own approval")

        # view then yes
        (ws / "hello.py").write_text("\n".join(f"print({i})" for i in range(100)) + "\n")
        shown = []
        ask = Asker("view", "yes")
        res = review_command("python hello.py", ws, set(), ask=ask, out=shown.append)
        text = "\n".join(shown)
        check(res is None and ask.calls == 2 and "print(99)" in text, "view shows the full script, then yes works")
        check("more lines" in text, "long scripts are previewed truncated with a view hint")

        # EOF on prompt = deny
        ask = Asker()   # no answers -> EOFError
        res = review_command("python hello.py", ws, set(), ask=ask, out=quiet)
        check(res and res.startswith("DENIED:"), "input closed (EOF) -> denied, not allowed")

        # anything but yes/y denies
        for junk in ["", "maybe", "yess", "ok", "YES PLEASE"]:
            res = review_command("python hello.py", ws, set(), ask=Asker(junk), out=quiet)
            check(res and res.startswith("DENIED:"), f"answer {junk!r} -> denied")

        # missing script
        items = find_scripts_needing_approval("python nothere.py", ws, set())
        check(items == [], "running a missing script alone needs no approval (it just fails)")
        items = find_scripts_needing_approval("echo 'print(1)' > evil.py && python evil.py", ws, set())
        check(len(items) == 1 and "may create it" in items[0]["reason"],
              "create-and-run in one command needs approval")
        items = find_scripts_needing_approval("printf x | tee evil.py; python evil.py", ws, set())
        check(len(items) == 1, "create via tee then run in one command needs approval")

        # outside the workspace: asked every time
        for cmd in [f"python {outside}", "python ../outside.py"]:
            appr = set()
            r1 = review_command(cmd, ws, appr, ask=Asker("yes"), out=quiet)
            ask = Asker("yes")
            review_command(cmd, ws, appr, ask=ask, out=quiet)
            check(r1 is None and ask.calls == 1 and not appr, f"outside script asked EVERY time ({cmd.split()[-1][-12:]})")

        # symlink pointing outside the workspace
        try:
            os.symlink(outside, ws / "link.py")
            items = find_scripts_needing_approval("python link.py", ws, set())
            check(len(items) == 1 and "OUTSIDE" in items[0]["reason"], "symlink to outside file is caught")
        except (OSError, NotImplementedError):
            print("SKIP: symlinks not supported on this filesystem")

        # unresolvable paths: asked every time, not remembered
        for cmd in ["python $FILE", "python ~/x.py", "python *.py", "python `cat name`",
                    "python $(cat name)", "xargs -I{} python {}"]:
            appr = set()
            items = find_scripts_needing_approval(cmd, ws, appr)
            r = review_command(cmd, ws, appr, ask=Asker("yes"), out=quiet)
            ask = Asker("no")
            r2 = review_command(cmd, ws, appr, ask=ask, out=quiet)
            check(items and r is None and ask.calls == 1 and r2.startswith("DENIED"),
                  f"unresolvable path asked every time: {cmd!r}")

        # cd earlier in the command: relative paths can't be trusted
        appr = set()
        review_command("python hello.py", ws, appr, ask=Asker("yes"), out=quiet)   # approve workspace/hello.py
        items = find_scripts_needing_approval("cd sub && python hello.py", ws, appr)
        check(len(items) == 1 and "cd" in items[0]["reason"],
              "'cd sub && python hello.py' is NOT covered by approval of workspace/hello.py")

        # directories and modules
        (ws / "pkg").mkdir()
        (ws / "pkg" / "__main__.py").write_text("print('pkg')\n")
        items = find_scripts_needing_approval("python pkg", ws, set())
        check(len(items) == 1 and "folder" in items[0]["reason"], "running a whole folder needs approval")
        items = find_scripts_needing_approval("python -m mymod", ws, set())
        check(len(items) == 1 and "mymod" in items[0]["display"], "python -m on a workspace module needs approval")
        items = find_scripts_needing_approval("python -m pytest", ws, set())
        check(items == [], "python -m pytest (not workspace code) is not flagged (documented gap)")

        # several scripts in one command
        (ws / "b.js").write_text("console.log(1)\n")
        appr = set()
        ask = Asker("yes", "yes")
        res = review_command("python hello.py && node b.js", ws, appr, ask=ask, out=quiet)
        check(res is None and ask.calls == 2 and len(appr) == 2, "two scripts -> two prompts, both remembered")
        ask = Asker("no")
        res = review_command("python sub/a.py; node b.js", ws, set(), ask=ask, out=quiet)
        check(res.startswith("DENIED") and ask.calls == 1, "denying the first script stops the command (second not asked)")

        # heredoc / stdin script
        ask = Asker("no")
        res = review_command("python - <<EOF\nimport os\nEOF", ws, set(), ask=ask, out=quiet)
        check(res.startswith("DENIED") and ask.calls == 1, "heredoc script is asked about (cannot be inspected)")

        # shell -c wrapper
        ask = Asker("no")
        res = review_command("sh -c 'python sub/a.py'", ws, set(), ask=ask, out=quiet)
        check(res.startswith("DENIED") and ask.calls == 1, "sh -c cannot hide a script run")

        # plain commands pass straight through
        for cmd in ["ls -la", "git status", "pip install requests", "cat hello.py", "echo done"]:
            ask = Asker()
            check(review_command(cmd, ws, set(), ask=ask, out=quiet) is None and ask.calls == 0,
                  f"ordinary command not asked: {cmd!r}")

        # too many files to fingerprint -> asked every time
        big = ws / "big"
        big.mkdir()
        for i in range(sg.MAX_FINGERPRINT_FILES + 5):
            (big / f"f{i}.py").write_text("pass\n")
        fp, n = fingerprint_script(big / "f0.py")
        check(fp is None and n > sg.MAX_FINGERPRINT_FILES, "huge folders can't be fingerprinted")
        appr = set()
        review_command("python big/f0.py", ws, appr, ask=Asker("yes"), out=quiet)
        ask = Asker("yes")
        review_command("python big/f0.py", ws, appr, ask=ask, out=quiet)
        check(ask.calls == 1 and not appr, "unfingerprintable script asked every time")

        # fingerprint is deterministic and content-sensitive
        a1, _ = fingerprint_script(ws / "sub" / "a.py")
        a2, _ = fingerprint_script(ws / "sub" / "a.py")
        (ws / "sub" / "a.py").write_text("print('different')\n")
        a3, _ = fingerprint_script(ws / "sub" / "a.py")
        check(a1 == a2 and a1 != a3, "fingerprint is stable, and changes when content changes")

    # ---------------- the false alarm seen on the phone ----------------
    with tempfile.TemporaryDirectory() as tmp5:
        ws5 = Path(tmp5).resolve()
        ask = Asker()
        res = review_command(
            "python --version && pip --version && node --version 2>/dev/null; npm --version 2>/dev/null",
            ws5, set(), ask=ask, out=quiet)
        check(res is None and ask.calls == 0, "version checks with 2>/dev/null no longer ask 'Run this script?'")
    check("ask or ask_human" in Path(__file__).with_name("script_gate.py").read_text(encoding="utf-8"),
          "script gate prompts through ask_human (fresh answers only)")

    # ---------------- wiring into ai.py (source check) ----------------
    src = Path(__file__).with_name("ai.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    check("from script_gate import review_command" in src, "ai.py imports review_command")
    check("SCRIPT_APPROVALS = set()" in src, "ai.py keeps a per-session approval set")
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "gated_run_command"), None)
    review_lines = [c.lineno for c in ast.walk(fn) if isinstance(c, ast.Call)
                    and getattr(c.func, "id", "") == "review_command"] if fn else []
    run_lines = [c.lineno for c in ast.walk(fn) if isinstance(c, ast.Call)
                 and getattr(c.func, "id", "") == "run_command"] if fn else []
    check(bool(review_lines) and bool(run_lines) and max(review_lines) < min(run_lines),
          "gated_run_command calls review_command BEFORE run_command")
    all_calls = [c for c in ast.walk(tree) if isinstance(c, ast.Call)
                 and getattr(c.func, "id", "") == "run_command"]
    check(len(all_calls) == 1 and fn is not None and all_calls[0] in list(ast.walk(fn)),
          "run_command is only called from inside gated_run_command (no side door)")

    # ---------------- the REAL gated_run_command from ai.py, stubbed edges ----------------
    import builtins
    import contextlib
    import io
    from action_gate import classify_command

    ns_src = src.replace("\r\n", "\n")
    fn_src = ast.get_source_segment(ns_src, next(
        n for n in ast.parse(ns_src).body if isinstance(n, ast.FunctionDef) and n.name == "gated_run_command"))
    with tempfile.TemporaryDirectory() as tmp2:
        ws2 = Path(tmp2).resolve()
        (ws2 / "hello.py").write_text("print('hi')\n")
        ran = []
        namespace = {
            "classify_command": classify_command,
            "review_command": review_command,
            "SCRIPT_APPROVALS": set(),
            "SCRIPT_DENIALS": set(),
            "WORKSPACE": ws2,
            "run_command": lambda cmd: ran.append(cmd) or "ran:" + cmd,
        }
        exec(fn_src, namespace)
        gated = namespace["gated_run_command"]
        real_input = builtins.input
        try:
            sink = io.StringIO()
            with contextlib.redirect_stdout(sink):
                builtins.input = Asker("no")
                out1 = gated("python hello.py")
                check_denied = out1.startswith("DENIED:") and ran == []
                namespace["SCRIPT_DENIALS"].clear()   # the human sends a new message
                builtins.input = Asker("yes")
                out2 = gated("python hello.py")
                check_ran = out2 == "ran:python hello.py" and ran == ["python hello.py"]
                builtins.input = Asker()
                out3 = gated("python hello.py")
                check_cached = out3 == "ran:python hello.py" and len(ran) == 2
                out4 = gated("ls -la")
                check_plain = out4 == "ran:ls -la" and len(ran) == 3
                (ws2 / "hello.py").write_text("print('tampered')\n")
                namespace["SCRIPT_DENIALS"].clear()
                builtins.input = Asker("no")
                out5 = gated("python hello.py")
                check_tamper = out5.startswith("DENIED:") and len(ran) == 3
                builtins.input = Asker()
                out6 = gated("rm -rf /")
                check_block = out6.startswith("BLOCKED:") and len(ran) == 3
        finally:
            builtins.input = real_input
        check(check_denied, "real gated_run_command: 'no' -> script NOT executed, DENIED returned")
        check(check_ran, "real gated_run_command: 'yes' -> script executed")
        check(check_cached, "real gated_run_command: same script again runs without asking")
        check(check_plain, "real gated_run_command: ordinary command unaffected")
        check(check_tamper, "real gated_run_command: edited script is asked again and denied")
        check(check_block, "real gated_run_command: BLOCK tier still blocks (nothing ran)")

    # ---------------- retry loop: a 'no' must stick (reported on the phone) ----------------
    with tempfile.TemporaryDirectory() as tmp3:
        ws3 = Path(tmp3).resolve()
        (ws3 / "hello.py").write_text("print('hi')\n")
        approved3, denied3 = set(), set()
        ask = Asker("no")
        first = review_command("python hello.py", ws3, approved3, ask=ask, out=quiet, denied=denied3)
        replies = [review_command("python hello.py", ws3, approved3, ask=ask, out=quiet, denied=denied3)
                   for _ in range(5)]
        check(first.startswith("DENIED:") and all(r.startswith("DENIED:") for r in replies) and ask.calls == 1,
              "after one 'no', the model retrying 5 times is NOT asked again (asked once total)")
        check("Do not retry" in first and "Stop" in first, "denial message tells the model to stop and not retry")
        check(approved3 == set(), "a denied script is never added to approvals")

        denied3.clear()   # human types a new message
        ask = Asker("yes")
        res = review_command("python hello.py", ws3, approved3, ask=ask, out=quiet, denied=denied3)
        check(res is None and ask.calls == 1, "after a new message, the script can be approved")

        approved3.clear()
        denied3.clear()
        review_command("python hello.py", ws3, approved3, ask=Asker("no"), out=quiet, denied=denied3)
        (ws3 / "hello.py").write_text("print('rewritten')\n")
        ask = Asker("no")
        review_command("python hello.py", ws3, approved3, ask=ask, out=quiet, denied=denied3)
        check(ask.calls == 1, "a rewritten script after a 'no' is a different script and is asked about")

        ask = Asker("no")
        review_command("python $X", ws3, approved3, ask=ask, out=quiet, denied=denied3)
        review_command("python $X", ws3, approved3, ask=ask, out=quiet, denied=denied3)
        check(ask.calls == 1, "denial also sticks for scripts with no fingerprint (unresolvable path)")

    # the real function, simulating the model hammering the same command
    with tempfile.TemporaryDirectory() as tmp4:
        import builtins as _b
        import contextlib as _c
        import io as _io
        ws4 = Path(tmp4).resolve()
        (ws4 / "hello.py").write_text("print('hi')\n")
        ran4 = []
        ns4 = {"classify_command": __import__("action_gate").classify_command,
               "review_command": review_command, "SCRIPT_APPROVALS": set(),
               "SCRIPT_DENIALS": set(), "WORKSPACE": ws4,
               "run_command": lambda cmd: ran4.append(cmd) or "ran"}
        exec(fn_src, ns4)
        ask4 = Asker("no")
        real_input = _b.input
        try:
            _b.input = ask4
            with _c.redirect_stdout(_io.StringIO()):
                outs = [ns4["gated_run_command"]("python hello.py") for _ in range(6)]
        finally:
            _b.input = real_input
        check(ask4.calls == 1 and ran4 == [] and all(o.startswith("DENIED:") for o in outs),
              "real gated_run_command: 6 retries after one 'no' -> asked once, never executed")

    check("SCRIPT_DENIALS.clear()" in src, "ai.py clears denials when the human sends a new message")
    check("denied=SCRIPT_DENIALS" in src, "ai.py passes the denial set to review_command")
    check("Do not retry it or work around it" in src, "ai.py's ordinary 'no' message also tells the model to stop")

    passed, total = sum(results), len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")
    print("NOTE: ai.py itself is not run here (it starts its chat loop on import).")
    print("      Do the live check on the phone.")
    if passed == total:
        print("[SUCCESS] Script gate verified.")
    else:
        print("[FAILURE] Some tests failed — review above.")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
