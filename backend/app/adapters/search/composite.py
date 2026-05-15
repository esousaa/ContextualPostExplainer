import asyncio

import structlog

from app.domain.errors import ExternalProviderError
from app.domain.models import SearchResult
from app.ports.search_provider import SearchProvider

logger = structlog.get_logger(__name__)


class CompositeSearchProvider(SearchProvider):
    def __init__(self, providers: list[SearchProvider]) -> None:
        self._providers = providers

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if not self._providers:
            raise ExternalProviderError("Composite search has no configured providers.")

        responses = await asyncio.gather(
            *[provider.search(query, max_results=max_results) for provider in self._providers],
            return_exceptions=True,
        )

        results: list[SearchResult] = []
        failures: list[str] = []
        for response in responses:
            if isinstance(response, Exception):
                failures.append(str(response))
                logger.warning("composite_search_provider_failed", error=str(response))
                continue
            results.extend(response)

        if not results and failures:
            raise ExternalProviderError("All configured search providers failed.")

        return results
