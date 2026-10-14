"""
Static checks on ai.py's text (ai.py starts its chat loop when imported,
so it can't be loaded in a test; these tests read its source).

Run directly: python test_ai_source.py
"""

import ast
import sys
from pathlib import Path

results = []


def check(ok, label):
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    results.append(bool(ok))


def run_all_tests():
    src = Path(__file__).with_name("ai.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    tree = ast.parse(src)

    assign = next((n for n in tree.body if isinstance(n, ast.Assign)
                   and any(getattr(t, "id", "") == "SYSTEM_PROMPT" for t in n.targets)), None)
    check(assign is not None, "ai.py defines SYSTEM_PROMPT")
    prompt = ast.get_source_segment(src, assign) if assign else ""

    check("Termux" in prompt, "system prompt says the agent runs in Termux")
    check('launched with "python"' in prompt, 'system prompt says to launch Python with "python"')
    check("NOT Windows" in prompt, "system prompt says plainly that this is NOT Windows")
    check("Prefer commands that work in Windows CMD" not in prompt, "system prompt no longer tells the model to prefer Windows CMD")
    check("Do not use Windows CMD or PowerShell" in prompt, "system prompt tells the model to use POSIX commands, not CMD/PowerShell")
    check('"py", not' not in prompt, 'system prompt no longer says to launch Python with "py"')
    check("Command Prompt" not in src, "no Windows 'Command Prompt' advice left anywhere in ai.py")
    check("export OPENROUTER_API_KEY" in src, "missing-API-key message tells the user how to set it in Termux")

    # --- M7.3: working order and honesty rules in the prompt ---
    check("OBEY THE USER'S ORDER OF WORK" in prompt, "system prompt has the 'obey the order of work' rules")
    check("inspect, plan, or report first, do ONLY that" in prompt, "prompt: inspect/plan/report-first means do only that")
    check("do not start building on guesses" in prompt, "prompt: do not build on guesses after a denial or failure")
    check("Only state facts" in prompt and "from a tool" in prompt, "prompt: only state facts that came from a tool")
    check("never hardcode secrets" in prompt, "prompt: never fabricate data or hardcode secrets")
    check("Do not merely explain" not in prompt, "prompt no longer pushes 'build, don't explain' unconditionally")
    inspect_pos = prompt.find("Inspect what already exists")
    create_pos = prompt.find("Create the necessary folders and files")
    check(0 < inspect_pos < create_pos, "prompt step order: inspect BEFORE creating files")

    # --- M7.3: input handling ---
    input_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "input"]
    check(input_calls == [], "ai.py never calls bare input() (pastes and approvals go through console_input)")
    check("read_message(" in src and "ask_human(" in src, "ai.py reads messages with read_message and asks approvals with ask_human")
    check("The model returned an empty reply" in src, "an empty model reply is reported, not printed as 'None'")

    passed, total = sum(results), len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")
    print("[SUCCESS] ai.py text checks verified." if passed == total else "[FAILURE] Some tests failed — review above.")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
