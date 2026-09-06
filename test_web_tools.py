"""
Test suite for web_tools.py

Run directly: python test_web_tools.py
No network needed for these tests — they cover the URL safety
checks and HTML extraction logic in isolation. The actual live
fetch_url() network call still needs to be verified on a real
device with internet access; these tests cannot confirm that.
"""

from web_tools import is_safe_url, extract_text_from_html


def run_all_tests():
    results = []

    # --- is_safe_url tests ---

    safety_cases = [
        ("https://api.open-meteo.com/v1/forecast", True),
        ("http://example.com", True),
        ("https://power.larc.nasa.gov/docs", True),
        ("ftp://example.com/file", False),          # wrong scheme
        ("file:///etc/passwd", False),               # wrong scheme
        ("http://localhost/admin", False),           # private host
        ("http://127.0.0.1:8080", False),            # private host
        ("http://192.168.1.1/router", False),        # private host
        ("http://10.0.0.5/internal", False),         # private host
        ("http://169.254.169.254/latest/meta-data", False),  # cloud metadata endpoint
    ]

    for url, expected_safe in safety_cases:
        safe, reason = is_safe_url(url)
        ok = safe == expected_safe
        status = "PASS" if ok else "FAIL"
        print(f"{status}: is_safe_url(\"{url}\") -> {safe} (expected {expected_safe})")
        results.append(ok)

    # --- extract_text_from_html tests ---

    html1 = "<html><body><h1>Hello</h1><p>World</p></body></html>"
    text1 = extract_text_from_html(html1)
    ok = "Hello" in text1 and "World" in text1 and "<" not in text1
    print(f"{'PASS' if ok else 'FAIL'}: extract_text_from_html strips tags, keeps content")
    results.append(ok)

    html2 = "<html><script>alert('xss')</script><body>Real content</body></html>"
    text2 = extract_text_from_html(html2)
    ok = "alert" not in text2 and "Real content" in text2
    print(f"{'PASS' if ok else 'FAIL'}: extract_text_from_html strips script contents")
    results.append(ok)

    html3 = "<div>   Lots\n\n   of   \t whitespace   </div>"
    text3 = extract_text_from_html(html3)
    ok = "  " not in text3  # no double-spaces left after collapsing
    print(f"{'PASS' if ok else 'FAIL'}: extract_text_from_html collapses whitespace")
    results.append(ok)

    passed = sum(results)
    total = len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")
    print("NOTE: fetch_url()'s actual live network call is NOT tested here —")
    print("      that requires a real device with internet access.")

    if passed == total:
        print("[SUCCESS] URL safety and HTML extraction logic verified.")
    else:
        print("[FAILURE] Some tests failed — review above.")

    return passed == total


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
