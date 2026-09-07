"""
Test suite for killswitch.py

Run directly: python test_killswitch.py
No network needed.
"""

from pathlib import Path
import shutil

from killswitch import killswitch_path, is_killed, activate, deactivate


def run_all_tests():
    test_dir = Path("test_killswitch_workspace")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()

    results = []

    # Starts inactive
    ok = is_killed(test_dir) == False
    print(f"{'PASS' if ok else 'FAIL'}: kill switch starts inactive")
    results.append(ok)

    # Activating creates the file and is_killed reflects it
    activate(test_dir, reason="test activation")
    ok = is_killed(test_dir) == True
    print(f"{'PASS' if ok else 'FAIL'}: activate() makes is_killed() true")
    results.append(ok)

    # The actual file exists at the expected path, readable
    path = killswitch_path(test_dir)
    ok = path.exists() and path.name == "KILLSWITCH"
    print(f"{'PASS' if ok else 'FAIL'}: file created at correct path with correct name")
    results.append(ok)

    ok = "test activation" in path.read_text()
    print(f"{'PASS' if ok else 'FAIL'}: activation reason is written to the file")
    results.append(ok)

    # Deactivating removes it
    deactivate(test_dir)
    ok = is_killed(test_dir) == False
    print(f"{'PASS' if ok else 'FAIL'}: deactivate() makes is_killed() false again")
    results.append(ok)

    # Deactivating when already off doesn't raise
    try:
        deactivate(test_dir)
        ok = True
    except Exception as e:
        ok = False
        print(f"    exception: {e}")
    print(f"{'PASS' if ok else 'FAIL'}: deactivate() is safe to call when already off")
    results.append(ok)

    # Activating twice in a row doesn't raise (idempotent)
    try:
        activate(test_dir)
        activate(test_dir)
        ok = is_killed(test_dir) == True
    except Exception as e:
        ok = False
        print(f"    exception: {e}")
    print(f"{'PASS' if ok else 'FAIL'}: activate() is safe to call twice")
    results.append(ok)

    deactivate(test_dir)
    shutil.rmtree(test_dir)

    passed = sum(results)
    total = len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("[SUCCESS] Kill switch logic verified.")
    else:
        print("[FAILURE] Some tests failed — review above.")

    return passed == total


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
