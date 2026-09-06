"""
Test suite for the Action Gate (action_gate.py)

Run directly: python test_action_gate.py
No API key or network needed — pure classification logic only.
"""

from action_gate import classify_command


FAKE_WORKSPACE = "/home/user/ObsidianAI/workspace"


def run_case(command, expected_tier, workspace_path=None):
    tier, reason = classify_command(command, workspace_path=workspace_path)
    ok = tier == expected_tier
    status = "PASS" if ok else "FAIL"
    print(f"{status}: \"{command}\" -> {tier} (expected {expected_tier})")
    return ok


def run_all_tests():
    cases = [
        # BLOCK — destructive, no override
        ("format C:", "BLOCK"),
        ("diskpart", "BLOCK"),
        ("shutdown /s /t 0", "BLOCK"),
        ("shutdown -h now", "BLOCK"),
        ("rm -rf /", "BLOCK"),
        ("rd /s /q C:\\", "BLOCK"),
        ("dd if=/dev/zero of=/dev/sda", "BLOCK"),
        ("DROP DATABASE production", "BLOCK"),

        # APPROVAL — risky, needs a yes/no from the terminal
        ("del test.txt", "APPROVAL"),
        ("rm oldfile.py", "APPROVAL"),
        ("rmdir old_folder", "APPROVAL"),
        ("git push origin main --force", "APPROVAL"),
        ("git push origin main -f", "APPROVAL"),
        ("git reset --hard HEAD~1", "APPROVAL"),
        ("git clean -fd", "APPROVAL"),
        ("DROP TABLE users", "APPROVAL"),
        ("chmod 777 script.sh", "APPROVAL"),

        # ALLOW — normal dev commands, must never be gated
        ("python ai.py", "ALLOW"),
        ("pip install requests", "ALLOW"),
        ("git status", "ALLOW"),
        ("git add .", "ALLOW"),
        ("git commit -m 'test'", "ALLOW"),
        ("ls -la", "ALLOW"),
        ("npm run dev", "ALLOW"),
        ("cat README.md", "ALLOW"),
    ]

    results = [run_case(cmd, expected) for cmd, expected in cases]

    # Path-escape detection — only triggers when workspace_path is provided
    escape_cases = [
        # Should be flagged APPROVAL — genuinely reach outside the workspace
        ("cd .. && del important.txt", "APPROVAL"),
        ("cat /etc/passwd", "APPROVAL"),
        ("type C:\\Windows\\System32\\config\\SAM", "APPROVAL"),
        ("cd ~ && ls", "APPROVAL"),
        ("cp secret.txt ../../outside.txt", "APPROVAL"),

        # Should NOT be flagged by the escape check — legitimately inside the workspace
        ("cat /home/user/ObsidianAI/workspace/notes.txt", "ALLOW"),
        ("python /home/user/ObsidianAI/workspace/script.py", "ALLOW"),
        ("git status", "ALLOW"),
        ("ls -la", "ALLOW"),
    ]

    print("\n-- Path-escape detection (workspace-aware) --")
    escape_results = [
        run_case(cmd, expected, workspace_path=FAKE_WORKSPACE)
        for cmd, expected in escape_cases
    ]
    results.extend(escape_results)

    passed = sum(results)
    total = len(results)

    print()
    print(f"RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("[SUCCESS] Action Gate classification verified.")
    else:
        print("[FAILURE] Some tests failed — review above before trusting this gate.")

    return passed == total


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
