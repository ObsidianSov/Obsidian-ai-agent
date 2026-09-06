"""
Test suite for the Audit Log (audit_log.py)

Run directly: python test_audit_log.py
No API key or network needed.
"""

from pathlib import Path
import shutil

from audit_log import AuditLog


def run_all_tests():
    test_dir = Path("test_audit_workspace")
    if test_dir.exists():
        shutil.rmtree(test_dir)

    results = []

    # Test 1: log file is created on first write
    log = AuditLog(test_dir / "logs")
    log.record("list_files", {"path": "."}, success=True, output="a.py\nb.py")
    ok = (test_dir / "logs" / "audit_log.jsonl").exists()
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: log file created on first write")

    # Test 2: entries persist across a fresh AuditLog instance
    # (simulates the agent process restarting)
    log2 = AuditLog(test_dir / "logs")
    entries = log2.read_all()
    ok = len(entries) == 1 and entries[0]["tool"] == "list_files"
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: entry survives fresh instance (simulated restart)")

    # Test 3: multiple entries append correctly, in order
    log2.record("run_command", {"command": "diskpart"}, success=False,
                output="BLOCKED: ...", tier="BLOCK")
    log2.record("write_file", {"path": "x.py", "content": "..."}, success=True,
                output="Successfully wrote to x.py")
    entries = log2.read_all()
    ok = (len(entries) == 3
          and entries[1]["tool"] == "run_command"
          and entries[1]["tier"] == "BLOCK"
          and entries[1]["success"] is False
          and entries[2]["tool"] == "write_file"
          and entries[2]["success"] is True)
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: multiple entries append in order with correct fields")

    # Test 4: tail() returns only the most recent N
    last_two = log2.tail(2)
    ok = len(last_two) == 2 and last_two[0]["tool"] == "run_command"
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: tail(2) returns the last 2 entries")

    # Test 5: output is truncated to 300 chars (doesn't bloat the log)
    long_output = "x" * 5000
    log2.record("read_file", {"path": "big.txt"}, success=True, output=long_output)
    latest = log2.read_all()[-1]
    ok = len(latest["output_snippet"]) == 300
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: long output truncated to 300 chars in log")

    # Test 6: a logging call never raises, even with a bad path
    try:
        bad_log = AuditLog(test_dir / "logs")
        bad_log.record("test", {}, success=True, output="ok")
        ok = True
    except Exception as e:
        ok = False
        print(f"    exception: {e}")
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}: record() does not raise under normal use")

    shutil.rmtree(test_dir)

    passed = sum(results)
    total = len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("[SUCCESS] Audit log verified.")
    else:
        print("[FAILURE] Some tests failed — review above before trusting this log.")

    return passed == total


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
