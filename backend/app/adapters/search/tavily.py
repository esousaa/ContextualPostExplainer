from typing import Any

import httpx
import structlog
from pydantic import SecretStr
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.domain.deduplication import canonicalize_url
from app.domain.errors import ExternalProviderError
from app.domain.models import SearchResult
from app.ports.search_provider import SearchProvider

logger = structlog.get_logger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class TavilySearchProvider(SearchProvider):
    def __init__(
        self,
        api_key: SecretStr,
        client: httpx.AsyncClient | None = None,
        endpoint: str = TAVILY_SEARCH_URL,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        logger.info("tavily_search_started", query=query, max_results=max_results)

        try:
            if self._client:
                payload = await self._request(self._client, query, max_results)
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    payload = await self._request(client, query, max_results)
        except httpx.TimeoutException as exc:
            raise ExternalProviderError("Tavily Search timed out.") from exc

        results = _normalize_results(payload, query=query, max_results=max_results)
        logger.info("tavily_search_completed", query=query, result_count=len(results))
        return results

    @retry(
        retry=retry_if_exception_type(httpx.TimeoutException),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=1.0),
        stop=stop_after_attempt(2),
        reraise=True,
    )
    async def _request(
        self,
        client: httpx.AsyncClient,
        query: str,
        max_results: int,
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                self._endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                },
                json={
                    "query": query,
                    "max_results": max(1, min(max_results, 20)),
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("tavily_search_http_error", status_code=exc.response.status_code)
            raise ExternalProviderError("Tavily Search returned an unexpected HTTP error.") from exc
        except httpx.TimeoutException as exc:
            logger.warning("tavily_search_timeout", query=query)
            raise exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("tavily_search_request_failed", error=str(exc))
            raise ExternalProviderError("Could not fetch search results from Tavily.") from exc

        if not isinstance(payload, dict):
            raise ExternalProviderError("Tavily Search returned an invalid response.")
        return payload


def _normalize_results(
    payload: dict[str, Any],
    query: str,
    max_results: int,
) -> list[SearchResult]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []

    results: list[SearchResult] = []
    for item in raw_results[:max_results]:
        if not isinstance(item, dict):
            continue

        title = _string(item.get("title"))
        url = _string(item.get("url"))
        snippet = _string(item.get("content"))
        if not title or not url:
            continue

        try:
            result = SearchResult(
                provider="tavily",
                query=query,
                title=title,
                url=url,
                snippet=snippet,
                rank=len(results) + 1,
                canonical_url=canonicalize_url(url),
            )
        except ValueError:
            logger.warning("tavily_search_result_discarded", reason="invalid_url", url=url)
            continue

        results.append(result)

    return results


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
