"""Web search through a user-configured SearXNG instance.

No hosted search API is called. The tool is off until
``tools.web_search.searxng_url`` or ``SEARXNG_URL`` is set. There is no
default public instance.
"""

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from agent.tools.base_tool import BaseTool, ToolResult
from common.log import logger
from config import conf


DEFAULT_TIMEOUT = 30
PROVIDER_ORDER = ["searxng"]


def _tools_web_search_conf() -> dict:
    tools_cfg = conf().get("tools") or {}
    if not isinstance(tools_cfg, dict):
        return {}
    block = tools_cfg.get("web_search") or {}
    return block if isinstance(block, dict) else {}


def _conf_str(value, default: str = "") -> str:
    return (value.strip() if isinstance(value, str) else "") or default


def _get_api_key(provider: str) -> str:
    """Hosted search keys are not read. SearXNG uses a URL, not a key."""
    del provider
    return ""


def anonymous_opt_in(value) -> bool:
    """Kept for older callers. Keyless hosted search is not offered."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return False


def _get_searxng_url() -> str:
    """Resolve the SearXNG instance URL. Empty when the user has not set one."""
    url = _conf_str(_tools_web_search_conf().get("searxng_url"), "")
    return url or os.environ.get("SEARXNG_URL", "").strip()


def parse_provider_list(raw) -> List[str]:
    if isinstance(raw, str):
        raw = raw.split(",")
    if not isinstance(raw, list):
        return []
    return [p.strip().lower() for p in raw if isinstance(p, str) and p.strip()]


def disabled_providers() -> List[str]:
    return parse_provider_list(_tools_web_search_conf().get("disabled_providers"))


def configured_providers() -> List[str]:
    """SearXNG only, and only when its URL is set and it is not disabled."""
    if "searxng" in set(disabled_providers()):
        return []
    return ["searxng"] if _get_searxng_url() else []


class WebSearch(BaseTool):
    """Search the web through the configured SearXNG instance."""

    name: str = "web_search"
    description: str = "Search the web for real-time information. Returns titles, URLs, and snippets."

    params: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string",
            },
            "count": {
                "type": "integer",
                "description": "Number of results to return (1-50, default: 10)",
            },
            "freshness": {
                "type": "string",
                "description": "Unused. SearXNG does not take a freshness filter here.",
            },
            "summary": {
                "type": "boolean",
                "description": "Unused. Results are the snippets SearXNG returns.",
            },
        },
        "required": ["query"],
    }

    def __init__(self, config: dict = None):
        self.config = config or {}

    @staticmethod
    def is_available() -> bool:
        return bool(configured_providers())

    def get_json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": json.loads(json.dumps(self.params)),
        }

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        query = (args.get("query") or "").strip()
        if not query:
            return ToolResult.fail("Error: 'query' parameter is required")
        count = args.get("count", 10)
        if not isinstance(count, int) or count < 1 or count > 50:
            count = 10
        if not _get_searxng_url():
            return ToolResult.fail(
                "Error: web search is off. Set tools.web_search.searxng_url to a SearXNG instance."
            )
        if "searxng" in set(disabled_providers()):
            return ToolResult.fail("Error: SearXNG search is disabled.")
        try:
            return self._search_searxng(query, count)
        except requests.Timeout:
            return ToolResult.fail("Error: SearXNG request timed out.")
        except requests.RequestException as exc:
            logger.error("[WebSearch] searxng request failed: %s", exc)
            return ToolResult.fail("Error: SearXNG request failed.")

    def _search_searxng(self, query: str, count: int) -> ToolResult:
        base_url = _get_searxng_url().rstrip("/")
        if not base_url:
            return ToolResult.fail(
                "Error: SearXNG instance URL not configured. Set tools.web_search.searxng_url or SEARXNG_URL."
            )
        params = {"q": query, "format": "json", "pageno": 1}
        language = _conf_str(_tools_web_search_conf().get("searxng_language"), "")
        if language:
            params["language"] = language
        categories = _conf_str(_tools_web_search_conf().get("searxng_categories"), "general")
        if categories:
            params["categories"] = categories
        url = f"{base_url}/search?{urlencode(params)}"
        headers = {"Accept": "application/json", "User-Agent": "Maia"}
        logger.debug("[WebSearch] searxng query=%r instance=%s", query, base_url)
        resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 401:
            return ToolResult.fail("Error: SearXNG instance requires authentication.")
        if resp.status_code == 403:
            return ToolResult.fail("Error: SearXNG instance access forbidden.")
        if resp.status_code == 429:
            return ToolResult.fail("Error: SearXNG rate limit reached.")
        if resp.status_code != 200:
            return ToolResult.fail(f"Error: SearXNG returned HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            data = resp.json()
        except (ValueError, TypeError):
            return ToolResult.fail("Error: SearXNG returned non-JSON. Enable format=json on the instance.")
        items = data.get("results") or []
        results = []
        for item in items[:max(1, min(int(count or 10), 50))]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content") or item.get("snippet", ""),
                "siteName": item.get("engine") or item.get("source") or "",
                "score": item.get("score"),
            })
        return ToolResult.success({
            "query": query,
            "backend": "searxng",
            "total": len(results),
            "count": len(results),
            "results": results,
        })
