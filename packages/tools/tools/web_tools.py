"""Web MCP server — search + fetch.

Search uses DuckDuckGo via the `ddgs` package (no API key). Fetch uses httpx
+ trafilatura to pull cleaned article text.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web-tools")


def _denylist() -> set[str]:
    raw = os.environ.get("WEB_FETCH_DENYLIST", "")
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


@mcp.tool()
def search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Web search. Returns a list of {title, url, snippet}."""
    from ddgs import DDGS  # imported lazily — heavy module, test-friendly

    results: list[dict[str, str]] = []
    with DDGS() as ddg:
        for r in ddg.text(query, max_results=max_results):
            results.append(
                {
                    "title": r.get("title") or "",
                    "url": r.get("href") or r.get("url") or "",
                    "snippet": r.get("body") or "",
                }
            )
    return results


@mcp.tool()
def fetch(url: str, max_chars: int = 20_000) -> str:
    """Fetch a URL and return cleaned article text.

    Respects WEB_FETCH_DENYLIST. Text is truncated to `max_chars` so an agent
    can't blow through its context with one page.
    """
    host = (urlparse(url).hostname or "").lower()
    if host in _denylist():
        raise PermissionError(f"Host is denylisted: {host}")

    import trafilatura  # lazy — heavy import

    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        resp = client.get(url, headers={"User-Agent": "orchestra-bot/0.0"})
        resp.raise_for_status()
        html = resp.text
    text = trafilatura.extract(html) or ""
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[... truncated ...]"
    return text


if __name__ == "__main__":
    mcp.run()
