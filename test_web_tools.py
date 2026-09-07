"""
Test suite for web_tools.py

Run directly: python test_web_tools.py
No network needed for these tests — they cover the URL safety
checks and HTML extraction logic in isolation. The actual live
fetch_url() network call still needs to be verified on a real
device with internet access; these tests cannot confirm that.
"""

from web_tools import is_safe_url, extract_text_from_html, parse_search_results


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

    # --- parse_search_results tests ---

    real_shaped_response = {
        "items": [
            {"title": "Open-Meteo Docs", "link": "https://open-meteo.com/en/docs", "snippet": "Free weather API"},
            {"title": "GitHub - open-meteo", "link": "https://github.com/open-meteo", "snippet": "Source code"},
        ]
    }
    parsed = parse_search_results(real_shaped_response)
    ok = "Open-Meteo Docs" in parsed and "GitHub - open-meteo" in parsed
    print(f"{'PASS' if ok else 'FAIL'}: parse_search_results extracts titles from real-shaped response")
    results.append(ok)

    ok = "https://open-meteo.com/en/docs" in parsed
    print(f"{'PASS' if ok else 'FAIL'}: parse_search_results extracts links")
    results.append(ok)

    empty_response = {"items": []}
    ok = parse_search_results(empty_response) == "No results found."
    print(f"{'PASS' if ok else 'FAIL'}: parse_search_results handles empty results gracefully")
    results.append(ok)

    no_items_key_response = {}
    ok = parse_search_results(no_items_key_response) == "No results found."
    print(f"{'PASS' if ok else 'FAIL'}: parse_search_results handles missing 'items' key (zero results)")
    results.append(ok)

    error_response = {"error": {"message": "API key not valid"}}
    ok = "API key not valid" in parse_search_results(error_response)
    print(f"{'PASS' if ok else 'FAIL'}: parse_search_results surfaces API errors clearly")
    results.append(ok)

    many_items_response = {
        "items": [{"title": f"Result {i}", "link": f"https://example.com/{i}", "snippet": ""} for i in range(10)]
    }
    limited = parse_search_results(many_items_response, max_results=3)
    ok = limited.count("- Result") == 3
    print(f"{'PASS' if ok else 'FAIL'}: parse_search_results respects max_results limit")
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
