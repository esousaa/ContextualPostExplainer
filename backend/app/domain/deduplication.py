from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha1
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.domain.models import Evidence, SearchResult

TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "msclkid"}


@dataclass(frozen=True)
class DeduplicationDiscard:
    id: str
    reason: str
    duplicate_of: str | None = None


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    path = parsed.path.rstrip("/")
    if not path:
        path = "/"

    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not _is_tracking_query_key(key)
    ]
    query = urlencode(sorted(query_items), doseq=True)

    return urlunparse((scheme, host, path, "", query, ""))


def stable_source_id(url: str, prefix: str = "src") -> str:
    digest = sha1(canonicalize_url(url).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def content_hash(content: str) -> str:
    normalized = " ".join(content.casefold().split())
    return sha1(normalized.encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    return " ".join(title.casefold().split())


def deduplicate_search_results(
    results: Iterable[SearchResult],
) -> tuple[list[SearchResult], list[DeduplicationDiscard]]:
    kept: list[SearchResult] = []
    discards: list[DeduplicationDiscard] = []
    seen: dict[str, SearchResult] = {}
    seen_indexes: dict[str, int] = {}
    seen_titles: dict[str, SearchResult] = {}
    seen_title_indexes: dict[str, int] = {}

    for result in results:
        canonical = canonicalize_url(result.url.unicode_string())
        previous = seen.get(canonical)
        if previous:
            merged = merge_search_result_provenance(previous, result)
            idx = seen_indexes[canonical]
            kept[idx] = merged
            seen[canonical] = merged
            merged_title_key = normalize_title(merged.title)
            seen_titles[merged_title_key] = merged
            seen_title_indexes[merged_title_key] = idx
            discards.append(
                DeduplicationDiscard(
                    id=result.url.unicode_string(),
                    reason="duplicate_canonical_url",
                    duplicate_of=previous.url.unicode_string(),
                )
            )
            continue

        title_key = normalize_title(result.title)
        previous_title = seen_titles.get(title_key)
        if title_key and previous_title:
            merged = merge_search_result_provenance(previous_title, result)
            kept[seen_title_indexes[title_key]] = merged
            seen_titles[title_key] = merged
            seen[canonicalize_url(merged.url.unicode_string())] = merged
            discards.append(
                DeduplicationDiscard(
                    id=result.url.unicode_string(),
                    reason="duplicate_title",
                    duplicate_of=previous_title.url.unicode_string(),
                )
            )
            continue

        normalized = _normalize_search_result_provenance(
            result.model_copy(update={"canonical_url": canonical})
        )
        seen[canonical] = normalized
        seen_indexes[canonical] = len(kept)
        seen_titles[title_key] = normalized
        seen_title_indexes[title_key] = len(kept)
        kept.append(normalized)

    return kept, discards


def deduplicate_evidence(
    evidence: Iterable[Evidence],
) -> tuple[list[Evidence], list[DeduplicationDiscard]]:
    kept: list[Evidence] = []
    discards: list[DeduplicationDiscard] = []
    seen_urls: dict[str, Evidence] = {}
    seen_url_indexes: dict[str, int] = {}
    seen_content: dict[str, Evidence] = {}
    seen_content_indexes: dict[str, int] = {}

    for item in evidence:
        normalized_item = normalize_evidence_provenance(item)
        canonical = item.canonical_url.unicode_string() if item.canonical_url else None
        if canonical:
            previous = seen_urls.get(canonical)
            if previous:
                merged = merge_evidence_provenance(previous, normalized_item)
                kept[seen_url_indexes[canonical]] = merged
                seen_urls[canonical] = merged
                seen_content[content_hash(merged.content)] = merged
                discards.append(
                    DeduplicationDiscard(
                        id=item.id,
                        reason="duplicate_canonical_url",
                        duplicate_of=previous.id,
                    )
                )
                continue

        digest = content_hash(normalized_item.content)
        previous_content = seen_content.get(digest)
        if previous_content:
            merged = merge_evidence_provenance(previous_content, normalized_item)
            kept[seen_content_indexes[digest]] = merged
            seen_content[digest] = merged
            if canonical:
                seen_urls[canonical] = merged
            discards.append(
                DeduplicationDiscard(
                    id=item.id,
                    reason="duplicate_content_hash",
                    duplicate_of=previous_content.id,
                )
            )
            continue

        if canonical:
            seen_urls[canonical] = normalized_item
            seen_url_indexes[canonical] = len(kept)
        seen_content[digest] = normalized_item
        seen_content_indexes[digest] = len(kept)
        kept.append(normalized_item)

    return kept, discards


def merge_search_result_provenance(
    left: SearchResult,
    right: SearchResult,
) -> SearchResult:
    providers = _unique([*_search_result_providers(left), *_search_result_providers(right)])
    provider_queries = _merge_provider_queries(
        _search_result_provider_queries(left),
        _search_result_provider_queries(right),
    )
    return left.model_copy(
        update={
            "provider": ", ".join(providers),
            "providers": providers,
            "provider_queries": provider_queries,
            "provider_result_count": len(providers),
            "query": _combined_query(provider_queries, left.query),
            "rank": min(left.rank, right.rank),
        }
    )


def normalize_evidence_provenance(evidence: Evidence) -> Evidence:
    providers = _evidence_providers(evidence)
    provider_queries = _evidence_provider_queries(evidence)
    return evidence.model_copy(
        update={
            "provider": ", ".join(providers) if providers else evidence.provider,
            "providers": providers,
            "provider_queries": provider_queries,
            "provider_result_count": max(1, len(providers)),
        }
    )


def merge_evidence_provenance(left: Evidence, right: Evidence) -> Evidence:
    providers = _unique([*_evidence_providers(left), *_evidence_providers(right)])
    provider_queries = _merge_provider_queries(
        _evidence_provider_queries(left),
        _evidence_provider_queries(right),
    )
    return left.model_copy(
        update={
            "provider": ", ".join(providers),
            "providers": providers,
            "provider_queries": provider_queries,
            "provider_result_count": max(1, len(providers)),
            "query": _combined_query(provider_queries, left.query),
        }
    )


def _is_tracking_query_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in TRACKING_QUERY_KEYS or normalized.startswith(TRACKING_QUERY_PREFIXES)


def _normalize_search_result_provenance(result: SearchResult) -> SearchResult:
    providers = _search_result_providers(result)
    provider_queries = _search_result_provider_queries(result)
    return result.model_copy(
        update={
            "provider": ", ".join(providers),
            "providers": providers,
            "provider_queries": provider_queries,
            "provider_result_count": len(providers),
        }
    )


def _search_result_providers(result: SearchResult) -> list[str]:
    return _unique([*result.providers, result.provider])


def _search_result_provider_queries(result: SearchResult) -> dict[str, list[str]]:
    queries = {provider: list(values) for provider, values in result.provider_queries.items()}
    for provider in _search_result_providers(result):
        values = queries.setdefault(provider, [])
        if result.query and result.query not in values:
            values.append(result.query)
    return queries


def _evidence_providers(evidence: Evidence) -> list[str]:
    values = [*evidence.providers]
    if evidence.provider:
        values.extend(part.strip() for part in evidence.provider.split(","))
    return _unique(values)


def _evidence_provider_queries(evidence: Evidence) -> dict[str, list[str]]:
    queries = {provider: list(values) for provider, values in evidence.provider_queries.items()}
    for provider in _evidence_providers(evidence):
        values = queries.setdefault(provider, [])
        if evidence.query and evidence.query not in values:
            values.append(evidence.query)
    return queries


def _merge_provider_queries(
    left: dict[str, list[str]],
    right: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged = {provider: list(values) for provider, values in left.items()}
    for provider, values in right.items():
        provider_values = merged.setdefault(provider, [])
        for value in values:
            if value not in provider_values:
                provider_values.append(value)
    return merged


def _combined_query(provider_queries: dict[str, list[str]], fallback: str | None) -> str:
    values = [
        query
        for queries in provider_queries.values()
        for query in queries
        if query
    ]
    unique_values = _unique(values)
    if unique_values:
        return " | ".join(unique_values[:4])
    return fallback or ""


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
