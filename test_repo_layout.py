"""
Test suite for the repo layout (M7)

Run directly: python test_repo_layout.py
Keeps the repo from drifting back into a mess: dead code, stale status
documents, or the agent's sandbox files getting committed.
Needs git (it asks git which files are tracked).
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
results = []


def check(ok, label):
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    results.append(bool(ok))


def read(rel):
    try:
        return (ROOT / rel).read_text(encoding="utf-8")
    except OSError:
        return ""


def tracked_files():
    proc = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return proc.stdout.splitlines()


def run_all_tests():
    files = tracked_files()
    check(files is not None and len(files) > 0, "git can list tracked files")
    if not files:
        return False

    # --- nothing from the old agent / side projects is tracked ---
    check(not any("agent_core" in f for f in files), "no tracked file belongs to the old agent_core")
    check(not any("raincast" in f.lower() for f in files), "no tracked RainCast files")
    check("ai_backup.py" not in files, "ai_backup.py is gone")

    # --- the agent's sandbox is not source code ---
    in_workspace = [f for f in files if f.startswith("workspace/")]
    check(in_workspace in ([], ["workspace/.gitkeep"]),
          f"only workspace/.gitkeep is tracked inside workspace/ (found: {in_workspace[:5]})")
    gitignore = read(".gitignore")
    check("workspace/*" in gitignore and "!workspace/.gitkeep" in gitignore,
          ".gitignore keeps the workspace sandbox out of git")

    # --- required project files exist and are tracked ---
    for needed in ["ai.py", "README.md", "docs/STATUS.md", "docs/BLUEPRINT.md", "requirements.txt"]:
        check(needed in files, f"{needed} is tracked")
    check("requests" in read("requirements.txt"),
          "requirements.txt lists requests")

    # --- no stale status documents anywhere except docs/STATUS.md ---
    stale = [f for f in files if re.search(r"(STATUS|PROJECT_STATE|CHANGE_REPORT)", Path(f).name, re.I)
             and f != "docs/STATUS.md"]
    check(stale == [], f"docs/STATUS.md is the only status document (found: {stale})")

    # --- no root module imports the removed agent ---
    root_py = [f for f in files if f.endswith(".py") and "/" not in f]
    offenders = [f for f in root_py if re.search(r"^\s*(import|from)\s+agent_core", read(f), re.M)]
    check(offenders == [], f"no root module imports agent_core (found: {offenders})")

    # --- every root test file is in the README's test command, and nothing extra ---
    test_files = sorted(Path(f).stem for f in root_py if Path(f).name.startswith("test_"))
    readme = read("README.md")
    loop = re.search(r"for t in ([^;]+); do", readme)
    listed = sorted(loop.group(1).split()) if loop else []
    check(listed == test_files, f"README test command lists exactly the test files (missing/extra: "
                                f"{sorted(set(test_files) ^ set(listed))})")

    # --- every module is mentioned in the README so docs can't silently rot ---
    modules = [Path(f).stem for f in root_py if not Path(f).name.startswith("test_") and f != "ai.py"]
    missing = [m for m in modules if f"{m}.py" not in readme]
    check(missing == [], f"README mentions every module (missing: {missing})")

    passed, total = sum(results), len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")
    print("[SUCCESS] Repo layout verified." if passed == total else "[FAILURE] Some tests failed — review above.")
    return passed == total


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
