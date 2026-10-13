"""
Test suite for console_input.py (M7.3)

Run directly: python test_console_input.py
Uses a pseudo-terminal (pty) so the code sees what it sees on the phone:
a real terminal where a paste arrives all at once. Unix only.

These tests exist because on the phone a pasted multi-line brief was
fed to the approval prompts as "answers" and reached the model in
pieces.
"""

import os
import select
import subprocess
import sys
import time
from pathlib import Path

try:
    import pty
except ImportError:
    pty = None

REPO = Path(__file__).resolve().parent
results = []


def check(ok, label):
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    results.append(bool(ok))


def run_in_terminal(code, chunks, tail=0.6, timeout=20):
    """Run python code in a pty. chunks = [(seconds_to_wait_after, text), ...]."""
    master, slave = pty.openpty()
    env = dict(os.environ, PYTHONPATH=str(REPO), PYTHONUNBUFFERED="1")
    proc = subprocess.Popen([sys.executable, "-c", code], stdin=slave, stdout=slave,
                            stderr=slave, close_fds=True, cwd=REPO, env=env)
    os.close(slave)
    out = b""

    def drain(seconds):
        nonlocal out
        end = time.time() + seconds
        while time.time() < end:
            ready, _, _ = select.select([master], [], [], 0.05)
            if ready:
                try:
                    out += os.read(master, 4096)
                except OSError:
                    return

    drain(0.6)
    for wait, text in chunks:
        os.write(master, text.encode())
        drain(wait)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
    drain(tail)
    os.close(master)
    return out.decode(errors="replace").replace("\r", "")


def lines_with(out, marker):
    # the marker can follow a prompt on the same line (the prompt has no newline)
    return [l.split(marker, 1)[1] for l in out.splitlines() if marker in l]


def run_all_tests():
    if pty is None or not hasattr(os, "openpty"):
        print("SKIP: no pseudo-terminal support here; these tests need Linux/Termux")
        return True

    paste = "PROJECT: dashboard\nPhase 1: inspect the zip\nDo not write files yet\nyes\n"

    # ---------- reading messages ----------
    code = ("from console_input import read_message\n"
            "m = read_message('You: ')\n"
            "print('GOT=' + repr(m))\n")
    out = run_in_terminal(code, [(1.2, paste), (0.8, "\n")])
    got = lines_with(out, "GOT=")
    check(got == [repr("PROJECT: dashboard\nPhase 1: inspect the zip\nDo not write files yet\nyes")],
          "a pasted 4-line brief arrives as ONE message (after Enter)")
    check("Pasted 4 lines. Press Enter to send" in out, "the human is told how many lines were pasted and to press Enter")

    out = run_in_terminal(code, [(1.2, "first line\nsecond line\nlast line with no line break"), (0.8, "\n")])
    check(lines_with(out, "GOT=") == [repr("first line\nsecond line\nlast line with no line break")],
          "a paste whose LAST line has no line break keeps that last line")

    out = run_in_terminal(code, [(1.2, paste)], tail=0.5, timeout=2)
    check(lines_with(out, "GOT=") == [], "nothing is sent until the human presses Enter after a multi-line paste")

    out = run_in_terminal(code, [(1.0, "just one line\n")])
    check(lines_with(out, "GOT=") == [repr("just one line")], "a single typed line is unchanged")

    code2 = ("from console_input import read_message\n"
             "print('A=' + repr(read_message('You: ')))\n"
             "print('B=' + repr(read_message('You: ')))\n")
    out = run_in_terminal(code2, [(1.0, "first\n"), (1.0, "second\n")])
    check(lines_with(out, "A=") == [repr("first")] and lines_with(out, "B=") == [repr("second")],
          "lines typed one at a time (with pauses) stay separate messages")

    out = run_in_terminal(code, [(1.2, "line one\nline two\n\n\n"), (0.8, "\n")])
    check(lines_with(out, "GOT=") == [repr("line one\nline two")], "trailing blank lines from a paste are trimmed")

    # ---------- approval prompts ----------
    ask_code = ("import time\n"
                "from console_input import read_message, ask_human\n"
                "first = read_message('You: ')\n"
                "print('FIRST_LINES=' + str(first.count(chr(10)) + 1))\n"
                "time.sleep(0.8)\n"
                "try:\n"
                "    ans = ask_human('Allow this command to run? (yes/no): ')\n"
                "    print('ANSWER=' + repr(ans))\n"
                "except EOFError:\n"
                "    print('ANSWER=EOF')\n")

    # paste arrives, agent is 'busy' 0.8s, then asks. A stray "yes" must NOT answer it.
    out = run_in_terminal(ask_code, [(0.3, paste), (0.5, "\n"), (1.2, ""), (0.8, "no\n")])
    check(lines_with(out, "ANSWER=") == [repr("no")],
          "approval prompt is answered only by what the human types AFTER it appears")

    # extra text pasted WHILE the agent is busy (after the first message was read)
    out = run_in_terminal(ask_code, [(0.3, "start working\n"), (0.3, "yes\nyes\nyes\n"), (1.4, ""), (0.8, "no\n")])
    check(lines_with(out, "ANSWER=") == [repr("no")],
          "'yes' lines pasted while the agent is busy cannot approve anything")

    # nothing fresh typed at all: closed input must not become an approval
    out = run_in_terminal(ask_code, [(0.3, "start working\n"), (0.3, "yes\n"), (1.4, ""), (0.8, "\x04")])
    check(lines_with(out, "ANSWER=") == ["EOF"], "leftover 'yes' + closed input -> no answer, never an approval")

    out = run_in_terminal(ask_code, [(0.3, "start working\n"), (1.4, ""), (0.8, "yes\n")])
    check(lines_with(out, "ANSWER=") == [repr("yes")], "a real, fresh 'yes' still works")
    check("Allow this command to run? (yes/no): " in out, "the prompt text is shown")

    # ---------- not a terminal: behave exactly like input() ----------
    proc = subprocess.run(
        [sys.executable, "-c",
         "from console_input import read_message, ask_human, flush_pending_input\n"
         "flush_pending_input()\n"
         "print(repr(read_message('')), repr(read_message('')), repr(ask_human('')))\n"],
        input="a\nb\nc\n", capture_output=True, text=True, cwd=REPO, env=dict(os.environ, PYTHONPATH=str(REPO)))
    check(proc.stdout.strip() == "'a' 'b' 'c'" and proc.returncode == 0,
          "piped input (tests, scripts) is read one line at a time, as before")

    passed, total = sum(results), len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")
    print("[SUCCESS] Console input verified." if passed == total else "[FAILURE] Some tests failed — review above.")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
