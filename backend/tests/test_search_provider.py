import httpx
import pytest
import respx
from pydantic import SecretStr

from app.adapters.search.brave import BRAVE_WEB_SEARCH_URL, BraveSearchProvider
from app.adapters.search.registry import get_live_search_provider
from app.config import Settings
from app.domain.errors import ExternalProviderError, SearchProviderRequiredError


def _settings(**overrides) -> Settings:
    values = {
        "openai_api_key": "test-openai-key",
        "openai_generation_model": "gpt-4o",
        "openai_judge_model": "gpt-4o-mini",
        "openai_embedding_model": "text-embedding-3-small",
        "backend_cors_origins": ["http://localhost:5173"],
        "eval_fixture_dir": "eval/fixtures",
        "brave_api_key": None,
        "tavily_api_key": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_live_search_registry_requires_matching_provider_key() -> None:
    settings = _settings(search_provider="brave")

    with pytest.raises(SearchProviderRequiredError):
        get_live_search_provider(settings)


def test_live_search_registry_returns_brave_provider() -> None:
    settings = _settings(search_provider="brave", brave_api_key="test-brave-key")

    provider = get_live_search_provider(settings)

    assert isinstance(provider, BraveSearchProvider)


@pytest.mark.asyncio
async def test_brave_search_provider_returns_normalized_results() -> None:
    with respx.mock:
        respx.get(BRAVE_WEB_SEARCH_URL).respond(
            json={
                "web": {
                    "results": [
                        {
                            "title": "Result one",
                            "url": "https://www.example.com/article/?utm_source=x",
                            "description": "First snippet",
                        },
                        {
                            "title": "Result two",
                            "url": "https://example.org",
                            "description": "Second snippet",
                        },
                    ]
                }
            }
        )

        async with httpx.AsyncClient() as client:
            provider = BraveSearchProvider(api_key=SecretStr("test-brave-key"), client=client)
            results = await provider.search("example query", max_results=5)

    assert len(results) == 2
    assert results[0].provider == "brave"
    assert results[0].query == "example query"
    assert results[0].rank == 1
    assert results[0].canonical_url is not None
    assert results[0].canonical_url.unicode_string() == "https://example.com/article?utm_source=x"


@pytest.mark.asyncio
async def test_brave_search_provider_returns_empty_list_for_empty_response() -> None:
    with respx.mock:
        respx.get(BRAVE_WEB_SEARCH_URL).respond(json={"web": {"results": []}})

        async with httpx.AsyncClient() as client:
            provider = BraveSearchProvider(api_key=SecretStr("test-brave-key"), client=client)
            results = await provider.search("unknown topic", max_results=5)

    assert results == []


@pytest.mark.asyncio
async def test_brave_search_provider_maps_http_error() -> None:
    with respx.mock:
        respx.get(BRAVE_WEB_SEARCH_URL).respond(status_code=500, json={"error": "upstream"})

        async with httpx.AsyncClient() as client:
            provider = BraveSearchProvider(api_key=SecretStr("test-brave-key"), client=client)

            with pytest.raises(ExternalProviderError):
                await provider.search("example query", max_results=5)


@pytest.mark.asyncio
async def test_brave_search_provider_retries_timeout_then_fails() -> None:
    with respx.mock:
        route = respx.get(BRAVE_WEB_SEARCH_URL).mock(side_effect=httpx.ReadTimeout("timeout"))

        async with httpx.AsyncClient() as client:
            provider = BraveSearchProvider(api_key=SecretStr("test-brave-key"), client=client)

            with pytest.raises(ExternalProviderError):
                await provider.search("example query", max_results=5)

    assert route.call_count == 2
