import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class SearchService:
    async def search(self, query: str, num_results: int = 5) -> str:
        """Query SearXNG and return formatted result text."""
        try:
            async with httpx.AsyncClient(timeout=settings.search_timeout) as client:
                r = await client.get(
                    f"{settings.searxng_url}/search",
                    params={"q": query, "format": "json"},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.error(f"SearXNG error: {e}")
            return f"[Search unavailable: {e}]"

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


search_service = SearchService()
