import httpx
import pytest
import respx
from pydantic import SecretStr

from app.adapters.search.brave import BraveSearchProvider
from app.adapters.search.composite import CompositeSearchProvider
from app.adapters.search.registry import get_live_search_provider
from app.adapters.search.tavily import TAVILY_SEARCH_URL, TavilySearchProvider
from app.config import Settings
from app.domain.models import SearchResult


def _settings(**overrides) -> Settings:
    values = {
        "openai_api_key": "test-openai-key",
        "openai_generation_model": "gpt-4o",
        "openai_judge_model": "gpt-4o-mini",
        "openai_embedding_model": "text-embedding-3-small",
        "backend_cors_origins": ["http://localhost:5173"],
        "eval_fixture_dir": "eval/fixtures",
    }
    values.update(overrides)
    return Settings(**values)


class FakeProvider:
    def __init__(self, provider: str, should_fail: bool = False) -> None:
        self._provider = provider
        self._should_fail = should_fail

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if self._should_fail:
            raise RuntimeError("provider failed")
        return [
            SearchResult(
                provider=self._provider,
                query=query,
                title=f"{self._provider} result",
                url=f"https://example.com/{self._provider}",
                snippet="Snippet",
                rank=1,
            )
        ][:max_results]


def test_registry_returns_tavily_provider() -> None:
    provider = get_live_search_provider(
        _settings(search_provider="tavily", tavily_api_key="test-tavily-key")
    )

    assert isinstance(provider, TavilySearchProvider)


def test_registry_returns_composite_provider() -> None:
    provider = get_live_search_provider(
        _settings(
            search_provider="composite",
            brave_api_key="test-brave-key",
            tavily_api_key="test-tavily-key",
        )
    )

    assert isinstance(provider, CompositeSearchProvider)


@pytest.mark.asyncio
async def test_tavily_search_provider_returns_normalized_results() -> None:
    with respx.mock:
        respx.post(TAVILY_SEARCH_URL).respond(
            json={
                "results": [
                    {
                        "title": "Tavily result",
                        "url": "https://www.example.com/page?utm_source=x",
                        "content": "Tavily snippet",
                    }
                ]
            }
        )

        async with httpx.AsyncClient() as client:
            provider = TavilySearchProvider(api_key=SecretStr("test-tavily-key"), client=client)
            results = await provider.search("query", max_results=5)

    assert len(results) == 1
    assert results[0].provider == "tavily"
    assert results[0].canonical_url is not None
    assert results[0].canonical_url.unicode_string() == "https://example.com/page"


@pytest.mark.asyncio
async def test_composite_search_keeps_results_when_one_provider_fails() -> None:
    provider = CompositeSearchProvider(
        [
            FakeProvider("brave"),
            FakeProvider("tavily", should_fail=True),
        ]
    )

    results = await provider.search("query", max_results=5)

    assert [result.provider for result in results] == ["brave"]


def test_brave_provider_still_available_for_single_provider_mode() -> None:
    provider = get_live_search_provider(
        _settings(search_provider="brave", brave_api_key="test-brave-key")
    )

    assert isinstance(provider, BraveSearchProvider)
