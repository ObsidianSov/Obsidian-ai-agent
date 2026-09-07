"""
Web fetch capability for Obsidian AI (ai.py)

Gives the agent the ability to fetch and read a real URL — the
capability that was missing today and forced every external fact
to be verified by a human instead of the agent itself.

This is NOT a search engine — it can only read a URL it's given,
not discover one. A separate decision is needed on search (API key
vs. scraping tradeoffs), deliberately not made here.

Includes basic SSRF protection: refuses to fetch internal/private
network addresses, so the agent can't be tricked into probing the
local machine or network under the guise of "fetch this URL".
"""

import re
import socket
from urllib.parse import urlparse

import requests

PRIVATE_HOST_PATTERNS = [
    r"^localhost$",
    r"^127\.",
    r"^0\.0\.0\.0$",
    r"^10\.",
    r"^192\.168\.",
    r"^172\.(1[6-9]|2\d|3[01])\.",
    r"^169\.254\.",   # link-local
    r"^::1$",
]


def is_safe_url(url: str):
    """
    Returns (is_safe: bool, reason: str or None).
    Blocks non-http(s) schemes and obviously internal/private hosts.
    This is a heuristic check, not a guarantee — DNS rebinding and
    similar advanced tricks are out of scope for this simple check.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Could not parse URL"

    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported scheme: {parsed.scheme}"

    hostname = parsed.hostname or ""

    for pattern in PRIVATE_HOST_PATTERNS:
        if re.match(pattern, hostname):
            return False, f"Refusing to fetch internal/private address: {hostname}"

    return True, None


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


def fetch_url(url: str, max_chars: int = 3000) -> str:
    """
    Fetch a URL and return readable text content, truncated to
    max_chars. Returns a clear error string on failure rather than
    raising, since this is called from the agent's tool loop.
    """
    safe, reason = is_safe_url(url)
    if not safe:
        return f"BLOCKED: {reason}"

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "ObsidianAI/1.0 (personal coding agent)"}
        )
    except requests.exceptions.Timeout:
        return f"Error: request to {url} timed out after 10 seconds"
    except requests.exceptions.RequestException as e:
        return f"Error fetching {url}: {e}"

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
