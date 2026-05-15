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
    seen_titles: dict[str, SearchResult] = {}

    for result in results:
        canonical = canonicalize_url(result.url.unicode_string())
        previous = seen.get(canonical)
        if previous:
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
            discards.append(
                DeduplicationDiscard(
                    id=result.url.unicode_string(),
                    reason="duplicate_title",
                    duplicate_of=previous_title.url.unicode_string(),
                )
            )
            continue

        seen[canonical] = result
        seen_titles[title_key] = result
        kept.append(result.model_copy(update={"canonical_url": canonical}))

    return kept, discards


def deduplicate_evidence(
    evidence: Iterable[Evidence],
) -> tuple[list[Evidence], list[DeduplicationDiscard]]:
    kept: list[Evidence] = []
    discards: list[DeduplicationDiscard] = []
    seen_urls: dict[str, Evidence] = {}
    seen_content: dict[str, Evidence] = {}

    for item in evidence:
        canonical = item.canonical_url.unicode_string() if item.canonical_url else None
        if canonical:
            previous = seen_urls.get(canonical)
            if previous:
                discards.append(
                    DeduplicationDiscard(
                        id=item.id,
                        reason="duplicate_canonical_url",
                        duplicate_of=previous.id,
                    )
                )
                continue

        digest = content_hash(item.content)
        previous_content = seen_content.get(digest)
        if previous_content:
            discards.append(
                DeduplicationDiscard(
                    id=item.id,
                    reason="duplicate_content_hash",
                    duplicate_of=previous_content.id,
                )
            )
            continue

        if canonical:
            seen_urls[canonical] = item
        seen_content[digest] = item
        kept.append(item)

    return kept, discards


def _is_tracking_query_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in TRACKING_QUERY_KEYS or normalized.startswith(TRACKING_QUERY_PREFIXES)
