"""
Test suite for web_tools.py

Run directly: python test_web_tools.py
No network needed: DNS and HTTP are faked, so these tests cover the
URL safety logic, redirect handling and HTML extraction in isolation.
The real network path (real DNS, real requests.get) is NOT tested
here and must be checked live on the phone.
"""

import ipaddress
import socket

from requests.structures import CaseInsensitiveDict

import web_tools
from web_tools import (
    is_safe_url, fetch_url, extract_text_from_html, parse_search_results,
)

results = []


def check(ok, label):
    print(f"{'PASS' if ok else 'FAIL'}: {label}")
    results.append(bool(ok))


PUBLIC_IP = ipaddress.ip_address("93.184.216.34")


def public_resolver(host, port):
    return [PUBLIC_IP]


class Recorder:
    """A resolver that records every call and answers from a map."""
    def __init__(self, mapping=None):
        self.mapping = mapping or {}
        self.calls = []

    def __call__(self, host, port):
        self.calls.append(host)
        answer = self.mapping.get(host, ["93.184.216.34"])
        if isinstance(answer, Exception):
            raise answer
        return [ipaddress.ip_address(a) for a in answer]


class FakeResponse:
    def __init__(self, status=200, headers=None, text=""):
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        self.text = text


def make_get(pages):
    """Fake requests.get. `pages` maps url -> FakeResponse. Records calls."""
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url not in pages:
            raise AssertionError(f"unexpected fetch of {url}")
        return pages[url]

    fake_get.calls = calls
    return fake_get


def redirect(to, status=302):
    return FakeResponse(status, {"Location": to})


def html_page(body):
    return FakeResponse(200, {"Content-Type": "text/html"}, body)


def run_all_tests():
    # --- original is_safe_url tests (names now use a fake DNS) ---
    original_cases = [
        ("https://api.open-meteo.com/v1/forecast", True),
        ("http://example.com", True),
        ("https://power.larc.nasa.gov/docs", True),
        ("ftp://example.com/file", False),
        ("file:///etc/passwd", False),
        ("http://localhost/admin", False),
        ("http://127.0.0.1:8080", False),
        ("http://192.168.1.1/router", False),
        ("http://10.0.0.5/internal", False),
        ("http://169.254.169.254/latest/meta-data", False),
    ]
    for url, expected in original_cases:
        safe, _ = is_safe_url(url, public_resolver)
        check(safe == expected, f'is_safe_url("{url}") -> {safe} (expected {expected})')

    # --- M5: IP literals in every spelling must be blocked ---
    rec = Recorder()
    blocked_literals = [
        "http://2130706433/",              # decimal 127.0.0.1
        "http://0x7f000001/",              # hex
        "http://0177.0.0.1/",              # octal
        "http://127.1/",                   # short form
        "http://0/",                       # 0.0.0.0
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://[::]/",
        "http://[::ffff:127.0.0.1]/",      # IPv4-mapped IPv6
        "http://[::ffff:7f00:1]/",         # same, hex form
        "http://[::ffff:10.0.0.1]/",
        "http://[::127.0.0.1]/",           # IPv4-compatible
        "http://[fd00::1]/",               # unique-local
        "http://[fc00::1]/",
        "http://[fe80::1]/",               # link-local
        "http://[64:ff9b::7f00:1]/",       # NAT64 wrapping 127.0.0.1
        "http://[2002:7f00:1::1]/",        # 6to4 wrapping 127.0.0.1
        "http://100.64.0.1/",              # CGNAT start
        "http://100.127.255.254/",         # CGNAT end
        "http://172.16.0.1/",
        "http://172.31.255.255/",
        "http://169.254.169.254/",
        "http://224.0.0.1/",               # multicast
        "http://198.18.0.1/",
    ]
    for url in blocked_literals:
        safe, _ = is_safe_url(url, rec)
        check(safe is False, f'blocks IP literal {url}')
    check(rec.calls == [], "IP literals are judged without any DNS lookup")

    # --- M5: legitimate public IPs must still work (no over-blocking) ---
    for url in ["http://8.8.8.8/", "https://[2606:4700:4700::1111]/",
                "http://100.63.255.255/", "http://172.32.0.1/"]:
        safe, _ = is_safe_url(url, rec)
        check(safe is True, f'allows public IP {url}')

    # --- M5: internal / metadata hostnames ---
    rec = Recorder()
    for url in ["http://metadata.google.internal/", "http://metadata/",
                "http://instance-data/", "http://localhost./",
                "http://LOCALHOST/", "http://foo.localhost/",
                "http://printer.local/", "http://db.internal/"]:
        safe, _ = is_safe_url(url, rec)
        check(safe is False, f'blocks internal hostname {url}')
    check(rec.calls == [], "internal hostnames are blocked before any DNS lookup")

    # --- M5: DNS answers decide for ordinary names ---
    safe, why = is_safe_url("http://foo.localtest.me/", Recorder({"foo.localtest.me": ["127.0.0.1"]}))
    check(safe is False and "resolves" in why, "blocks a name that resolves to 127.0.0.1")
    safe, _ = is_safe_url("http://mixed.example/", Recorder({"mixed.example": ["8.8.8.8", "10.0.0.1"]}))
    check(safe is False, "blocks if ANY resolved address is private")
    safe, _ = is_safe_url("http://v6.example/", Recorder({"v6.example": ["::1"]}))
    check(safe is False, "blocks a name that resolves to ::1")
    safe, _ = is_safe_url("http://v6map.example/", Recorder({"v6map.example": ["::ffff:127.0.0.1"]}))
    check(safe is False, "blocks a name that resolves to ::ffff:127.0.0.1")
    safe, _ = is_safe_url("http://nxdomain.example/", Recorder({"nxdomain.example": socket.gaierror("no such host")}))
    check(safe is False, "blocks when DNS lookup fails")
    safe, _ = is_safe_url("http://empty.example/", Recorder({"empty.example": []}))
    check(safe is False, "blocks when DNS returns no addresses")
    safe, _ = is_safe_url("https://good.example/page", Recorder({"good.example": ["8.8.8.8", "2606:4700:4700::1111"]}))
    check(safe is True, "allows a name that resolves only to public addresses")

    # --- M5: URL tricks / parser confusion ---
    tricks = [
        "http://user@127.0.0.1/",
        "http://example.com@127.0.0.1/",
        "http://127.0.0.1\\@example.com/",
        "http://exa mple.com/",
        "http://example.com/\r\nHost: evil",
        "http://\uff11\uff12\uff17.\uff10.\uff10.\uff11/",   # fullwidth 127.0.0.1
        "http://example.com:99999/",
        "http://[::1/",
        "gopher://example.com/",
        "javascript:alert(1)",
        "http:///nohost",
        "",
    ]
    for url in tricks:
        safe, _ = is_safe_url(url, public_resolver)
        check(safe is False, f'blocks URL trick {url!r}')

    # --- fetch_url: initial URL blocked => never fetched ---
    get = make_get({})
    out = fetch_url("http://0x7f000001/admin", _get=get, _resolver=public_resolver)
    check(out.startswith("BLOCKED") and get.calls == [], "fetch_url refuses a hex-IP URL and never makes the request")

    # --- fetch_url: redirects are re-checked on every hop ---
    for target, label in [
        ("http://127.0.0.1/secret", "127.0.0.1"),
        ("http://169.254.169.254/latest/meta-data/", "cloud metadata IP"),
        ("http://0x7f000001/", "hex-IP"),
        ("http://[::ffff:127.0.0.1]/", "IPv4-mapped IPv6"),
        ("http://metadata.google.internal/", "metadata hostname"),
        ("http://evil-dns.example/", "name that resolves to a private IP"),
    ]:
        get = make_get({"https://good.example/start": redirect(target)})
        res = Recorder({"evil-dns.example": ["192.168.0.10"]})
        out = fetch_url("https://good.example/start", _get=get, _resolver=res)
        check(out.startswith("BLOCKED: redirect") and len(get.calls) == 1,
              f"redirect to {label} is blocked and never fetched")

    pages = {
        "https://a.example/start": redirect("/middle", 301),
        "https://a.example/middle": redirect("https://b.example/final", 307),
        "https://b.example/final": html_page("<html><body><h1>Final</h1><p>Page</p></body></html>"),
    }
    get = make_get(pages)
    out = fetch_url("https://a.example/start", _get=get, _resolver=public_resolver)
    check("Final" in out and "Page" in out, "follows a safe redirect chain (relative + absolute) to the end")
    check(all(kw.get("allow_redirects") is False for _, kw in get.calls),
          "every request is sent with allow_redirects=False")

    loop = {"https://loop.example/a": redirect("https://loop.example/a")}
    out = fetch_url("https://loop.example/a", _get=make_get(loop), _resolver=public_resolver)
    check("too many redirects" in out, "redirect loop stops with a clear error")

    nohdr = {"https://x.example/": FakeResponse(302, {})}
    out = fetch_url("https://x.example/", _get=make_get(nohdr), _resolver=public_resolver)
    check("without a Location" in out, "redirect with no Location header gives a clear error")

    big = {"https://big.example/": FakeResponse(200, {"Content-Type": "text/plain"}, "x" * 5000)}
    out = fetch_url("https://big.example/", max_chars=100, _get=make_get(big), _resolver=public_resolver)
    check("truncated, 5000 total" in out, "fetch_url still truncates long content")

    binary = {"https://bin.example/": FakeResponse(200, {"Content-Type": "image/png"}, "")}
    out = fetch_url("https://bin.example/", _get=make_get(binary), _resolver=public_resolver)
    check(out.startswith("Unsupported content type"), "fetch_url still rejects non-text content")

    # --- extract_text_from_html tests ---
    text1 = extract_text_from_html("<html><body><h1>Hello</h1><p>World</p></body></html>")
    check("Hello" in text1 and "World" in text1 and "<" not in text1,
          "extract_text_from_html strips tags, keeps content")
    text2 = extract_text_from_html("<html><script>alert('xss')</script><body>Real content</body></html>")
    check("alert" not in text2 and "Real content" in text2, "extract_text_from_html strips script contents")
    text3 = extract_text_from_html("<div>   Lots\n\n   of   \t whitespace   </div>")
    check("  " not in text3, "extract_text_from_html collapses whitespace")

    # --- parse_search_results tests ---
    real_shaped = {"items": [
        {"title": "Open-Meteo Docs", "link": "https://open-meteo.com/en/docs", "snippet": "Free weather API"},
        {"title": "GitHub - open-meteo", "link": "https://github.com/open-meteo", "snippet": "Source code"},
    ]}
    parsed = parse_search_results(real_shaped)
    check("Open-Meteo Docs" in parsed and "GitHub - open-meteo" in parsed,
          "parse_search_results extracts titles from real-shaped response")
    check("https://open-meteo.com/en/docs" in parsed, "parse_search_results extracts links")
    check(parse_search_results({"items": []}) == "No results found.",
          "parse_search_results handles empty results gracefully")
    check(parse_search_results({}) == "No results found.",
          "parse_search_results handles missing 'items' key (zero results)")
    check("API key not valid" in parse_search_results({"error": {"message": "API key not valid"}}),
          "parse_search_results surfaces API errors clearly")
    many = {"items": [{"title": f"Result {i}", "link": f"https://example.com/{i}", "snippet": ""} for i in range(10)]}
    check(parse_search_results(many, max_results=3).count("- Result") == 3,
          "parse_search_results respects max_results limit")

    passed, total = sum(results), len(results)
    print()
    print(f"RESULTS: {passed}/{total} tests passed")
    print("NOTE: DNS and HTTP are faked here. The real network path and")
    print("      DNS rebinding are NOT tested; check live on the phone.")

    if passed == total:
        print("[SUCCESS] URL safety, redirect and HTML extraction logic verified.")
    else:
        print("[FAILURE] Some tests failed — review above.")
    return passed == total


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_all_tests() else 1)
