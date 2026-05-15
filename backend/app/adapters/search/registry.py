from app.adapters.search.brave import BraveSearchProvider
from app.adapters.search.composite import CompositeSearchProvider
from app.adapters.search.tavily import TavilySearchProvider
from app.config import Settings
from app.domain.errors import ConfigurationError
from app.ports.search_provider import SearchProvider


def get_live_search_provider(settings: Settings) -> SearchProvider:
    settings.require_live_search_provider()

    if settings.search_provider == "brave" and settings.brave_api_key is not None:
        return BraveSearchProvider(api_key=settings.brave_api_key)

    if settings.search_provider == "tavily" and settings.tavily_api_key is not None:
        return TavilySearchProvider(api_key=settings.tavily_api_key)

    if settings.search_provider == "composite":
        providers: list[SearchProvider] = []
        if settings.brave_api_key is not None:
            providers.append(BraveSearchProvider(api_key=settings.brave_api_key))
        if settings.tavily_api_key is not None:
            providers.append(TavilySearchProvider(api_key=settings.tavily_api_key))
        if providers:
            return CompositeSearchProvider(providers)

    raise ConfigurationError(f"Unsupported live search provider: {settings.search_provider}.")
