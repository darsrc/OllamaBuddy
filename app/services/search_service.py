import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=settings.search_timeout)
        return self._client

    async def search(self, query: str, num_results: int = 5) -> str:
        """Query SearXNG and return formatted result text."""
        try:
            client = await self._get_client()
            r = await client.get(
                f"{settings.searxng_url}/search",
                params={"q": query, "format": "json"},
            )
            r.raise_for_status()
            data = await r.json()
        except httpx.TimeoutException as e:
            logger.error(f"SearXNG timeout error: {e}")
            return f"[Search unavailable: Request timeout]"
        except httpx.HTTPStatusError as e:
            logger.error(f"SearXNG HTTP error: {e}")
            return f"[Search unavailable: HTTP {e.response.status_code}]"
        except httpx.RequestError as e:
            logger.error(f"SearXNG request error: {e}")
            return f"[Search unavailable: Request failed]"
        except Exception as e:
            logger.error(f"SearXNG unexpected error: {e}")
            return f"[Search unavailable: {type(e).__name__}]"

        results = data.get("results", [])[:num_results]
        if not results:
            return f"[No results found for: {query}]"

        lines = [f"Web search results for: {query}\n"]
        for i, res in enumerate(results, 1):
            title = res.get("title", "–")
            url = res.get("url", "")
            snippet = res.get("content", res.get("snippet", ""))[:300]
            lines.append(f"{i}. {title}")
            lines.append(f"   {url}")
            if snippet:
                lines.append(f"   {snippet}")
            lines.append("")

        return "\n".join(lines)

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


search_service = SearchService()
