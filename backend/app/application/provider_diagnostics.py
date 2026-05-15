from app.domain.deduplication import canonicalize_url
from app.domain.models import Evidence, SearchResult


def search_provider_diagnostics(results: list[SearchResult]) -> dict[str, object]:
    groups: dict[str, list[SearchResult]] = {}
    for result in results:
        canonical = _result_canonical_url(result)
        groups.setdefault(canonical, []).append(result)

    overlap = []
    for canonical_url, items in groups.items():
        providers = sorted({item.provider for item in items})
        if len(providers) < 2:
            continue
        overlap.append(
            {
                "canonical_url": canonical_url,
                "providers": providers,
                "result_count": len(items),
                "queries_by_provider": _queries_by_provider(items),
                "titles": sorted({item.title for item in items if item.title}),
            }
        )

    return {
        "search_provider_overlap": overlap,
        "search_provider_overlap_count": len(overlap),
    }


def provider_counts_for_sources(sources: list[Evidence]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        for provider in source_provider_names(source):
            counts[provider] = counts.get(provider, 0) + 1
    return counts


def multi_provider_source_count(sources: list[Evidence]) -> int:
    return sum(1 for source in sources if len(source_provider_names(source)) > 1)


def source_provider_names(source: Evidence) -> list[str]:
    if source.providers:
        return source.providers
    if source.provider:
        return [part.strip() for part in source.provider.split(",") if part.strip()]
    return []


def _result_canonical_url(result: SearchResult) -> str:
    if result.canonical_url:
        return result.canonical_url.unicode_string()
    return canonicalize_url(result.url.unicode_string())


def _queries_by_provider(items: list[SearchResult]) -> dict[str, list[str]]:
    queries: dict[str, list[str]] = {}
    for item in items:
        if not item.query:
            continue
        provider_queries = queries.setdefault(item.provider, [])
        if item.query not in provider_queries:
            provider_queries.append(item.query)
    return queries

