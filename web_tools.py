"""
Web fetch capability for Obsidian AI (ai.py)

Gives the agent the ability to fetch and read a real URL.
This is NOT a search engine — it can only read a URL it's given,
not discover one (web_search below does discovery).

SSRF protection (M5): the agent must not be tricked into reading
internal/private network addresses. The check:
  - allows only http/https, rejects credentials, backslashes,
    whitespace/control characters and non-ASCII hostnames
  - understands every IP spelling: decimal (2130706433), hex
    (0x7f000001), octal (0177.0.0.1), short (127.1), IPv6, and
    IPv4 hidden inside IPv6 (::ffff:127.0.0.1, 64:ff9b::, 6to4)
  - blocks private, loopback, link-local, CGNAT (100.64/10),
    IPv6 unique-local (fc00::/7, incl. fd00::/8), multicast and
    reserved ranges
  - blocks known internal/metadata hostnames
  - resolves DNS names and blocks if ANY resulting address is internal
  - follows redirects manually and re-checks EVERY hop

Known remaining limit: DNS rebinding. We validate the DNS answer,
then requests resolves the name again when it connects. A hostile
DNS server could answer differently the second time. Closing this
needs connecting to the validated IP directly; not done here.
"""

import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import requests

MAX_REDIRECTS = 5
REDIRECT_CODES = (301, 302, 303, 307, 308)

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata",
    "metadata.google.internal",
    "instance-data",
    "instance-data.ec2.internal",
    "kubernetes.default",
    "kubernetes.default.svc",
}
BLOCKED_SUFFIXES = (
    ".localhost", ".local", ".internal", ".localdomain",
    ".lan", ".home.arpa", ".intranet", ".corp",
)

# Belt and braces on top of ipaddress's is_global (its answers have
# changed between Python versions).
_EXTRA_BLOCKED_NETWORKS = [
    ipaddress.ip_network(n) for n in (
        "0.0.0.0/8",       # "this network" (0.0.0.0, "0")
        "100.64.0.0/10",   # carrier-grade NAT
        "127.0.0.0/8",     # loopback
        "169.254.0.0/16",  # link-local + cloud metadata
        "198.18.0.0/15",   # benchmarking
        "224.0.0.0/4",     # multicast
        "240.0.0.0/4",     # reserved
        "::/8",            # unspecified, loopback, IPv4-compatible
        "fc00::/7",        # unique-local (includes fd00::/8)
        "fe80::/10",       # link-local
        "ff00::/8",        # multicast
    )
]
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_6TO4 = ipaddress.ip_network("2002::/16")
_HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")
_BAD_URL_CHARS = re.compile(r"[\s\\\x00-\x1f\x7f]")


def _ip_is_blocked(ip) -> bool:
    """True if this IP address must never be fetched."""
    if isinstance(ip, ipaddress.IPv6Address):
        # IPv4 hidden inside IPv6: judge the embedded IPv4 address
        if ip.ipv4_mapped is not None:
            return _ip_is_blocked(ip.ipv4_mapped)
        if ip in _NAT64:
            return _ip_is_blocked(ipaddress.IPv4Address(ip.packed[-4:]))
        if ip in _6TO4:
            return _ip_is_blocked(ipaddress.IPv4Address(ip.packed[2:6]))
    if any(ip in net for net in _EXTRA_BLOCKED_NETWORKS):
        return True
    return not ip.is_global


def _parse_ip_literal(host: str):
    """Return an IP address object if host is ANY spelling of an IP
    address, else None."""
    try:
        return ipaddress.ip_address(host)   # IPv6, plain IPv4
    except ValueError:
        pass
    if not _HOSTNAME_RE.match(host):
        return None
    try:
        # Legacy IPv4 spellings: 2130706433, 0x7f000001, 0177.0.0.1, 127.1
        return ipaddress.IPv4Address(socket.inet_aton(host))
    except OSError:
        return None


def _default_resolver(host: str, port: int):
    infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    return [ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos]


def _check_host(host: str, port: int, resolver):
    host = host.rstrip(".").lower()
    if not host:
        return False, "Empty hostname"
    if not host.isascii():
        return False, "Non-ASCII hostnames are not allowed"

    ip = _parse_ip_literal(host)
    if ip is not None:
        if _ip_is_blocked(ip):
            return False, f"Refusing to fetch internal/private address: {host} ({ip})"
        return True, None

    if not _HOSTNAME_RE.match(host):
        return False, f"Invalid hostname: {host}"
    if host in BLOCKED_HOSTNAMES or host.endswith(BLOCKED_SUFFIXES):
        return False, f"Refusing to fetch internal hostname: {host}"

    try:
        ips = resolver(host, port)
    except (OSError, ValueError) as e:
        return False, f"Could not resolve {host}: {e}"
    if not ips:
        return False, f"Could not resolve {host}"
    for resolved in ips:
        if _ip_is_blocked(resolved):
            return False, f"{host} resolves to internal/private address {resolved}"
    return True, None


def is_safe_url(url: str, resolver=None):
    """
    Returns (is_safe: bool, reason: str or None).
    `resolver` is for tests only: a function (host, port) -> list of
    IP address objects. Real use leaves it None (real DNS).
    """
    resolver = resolver or _default_resolver

    if _BAD_URL_CHARS.search(url):
        return False, "URL contains whitespace, control or backslash characters"

    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return False, "Could not parse URL"

    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported scheme: {parsed.scheme}"
    if "@" in parsed.netloc:
        return False, "Credentials in URL are not allowed"

    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    return _check_host(parsed.hostname or "", port, resolver)


def extract_text_from_html(html: str) -> str:
    """
    Very simple HTML-to-text: strips script/style blocks entirely,
    strips remaining tags, collapses whitespace. Not a full parser —
    good enough for reading documentation/article pages.
    """
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url(url: str, max_chars: int = 3000, _get=None, _resolver=None) -> str:
    """
    Fetch a URL and return readable text content, truncated to
    max_chars. Returns a clear error string on failure rather than
    raising, since this is called from the agent's tool loop.
    Redirects are followed by hand so every hop is safety-checked.
    (_get and _resolver exist only so tests can run without a network.)
    """
    get = _get or requests.get
    current = url

    for hop in range(MAX_REDIRECTS + 1):
        safe, reason = is_safe_url(current, _resolver)
        if not safe:
            if hop == 0:
                return f"BLOCKED: {reason}"
            return f"BLOCKED: redirect to {current} refused: {reason}"

        try:
            response = get(
                current,
                timeout=10,
                headers={"User-Agent": "ObsidianAI/1.0 (personal coding agent)"},
                allow_redirects=False,
            )
        except requests.exceptions.Timeout:
            return f"Error: request to {current} timed out after 10 seconds"
        except requests.exceptions.RequestException as e:
            return f"Error fetching {current}: {e}"

        if response.status_code in REDIRECT_CODES:
            location = response.headers.get("Location")
            if not location:
                return f"Error: {current} redirected without a Location header"
            current = urljoin(current, location)
            continue
        break
    else:
        return f"Error: too many redirects (more than {MAX_REDIRECTS})"

    content_type = response.headers.get("Content-Type", "")

    if "html" in content_type:
        text = extract_text_from_html(response.text)
    elif "json" in content_type or "text" in content_type:
        text = response.text
    else:
        return f"Unsupported content type for reading as text: {content_type}"

    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated, {len(text)} total characters]"

    return text


def parse_search_results(data: dict, max_results: int = 5) -> str:
    """
    Turn Google Custom Search JSON API's raw response into readable
    text. Pure function, no network — testable against fabricated
    responses matching the real API's schema.
    """
    if "error" in data:
        message = data["error"].get("message", "unknown error")
        return f"Search API error: {message}"

    items = data.get("items", [])
    if not items:
        return "No results found."

    lines = []
    for item in items[:max_results]:
        title = item.get("title", "Untitled")
        link = item.get("link", "")
        snippet = item.get("snippet", "").replace("\n", " ")
        lines.append(f"- {title}\n  {link}\n  {snippet}")

    return "\n\n".join(lines)


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search using Google's Custom Search JSON API, restricted to
    whatever sites were configured in the Programmable Search Engine
    (this is NOT unrestricted whole-web search — see setup notes).
    Requires GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX environment
    variables to be set.
    """
    import os

    api_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
    cx = os.environ.get("GOOGLE_SEARCH_CX")

    if not api_key or not cx:
        return (
            "Search not configured: set the GOOGLE_SEARCH_API_KEY and "
            "GOOGLE_SEARCH_CX environment variables."
        )

    try:
        response = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cx,
                "q": query,
                "num": min(max_results, 10)
            },
            timeout=10
        )
        data = response.json()
    except requests.exceptions.Timeout:
        return "Error: search request timed out after 10 seconds"
    except requests.exceptions.RequestException as e:
        return f"Error performing search: {e}"

    return parse_search_results(data, max_results)
