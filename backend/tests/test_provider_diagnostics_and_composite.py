from datetime import UTC, datetime

import pytest

from app.application.provider_diagnostics import search_provider_diagnostics
from app.application.ranking import EvidenceRanker
from app.domain.deduplication import deduplicate_evidence, deduplicate_search_results
from app.domain.models import Evidence, PostAuthor, PostData, SearchResult

LONG_CONTENT = (
    "This source contains enough relevant extractable text to be eligible for "
    "ranking. It discusses the same public issue, the timeline, the affected "
    "entities, and the practical context that readers need to understand."
)


class CompositeBoostEmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def test_search_provider_diagnostics_reports_overlap() -> None:
    results = [
        _search_result("brave", "https://www.example.com/story?utm_source=brave"),
        _search_result("tavily", "https://example.com/story"),
        _search_result("tavily", "https://example.com/other"),
    ]

    diagnostics = search_provider_diagnostics(results)

    assert diagnostics["search_provider_overlap_count"] == 1
    overlap = diagnostics["search_provider_overlap"][0]
    assert overlap["canonical_url"] == "https://example.com/story"
    assert overlap["providers"] == ["brave", "tavily"]


def test_search_dedup_merges_provider_provenance() -> None:
    kept, discards = deduplicate_search_results(
        [
            _search_result("brave", "https://www.example.com/story?utm_source=brave"),
            _search_result("tavily", "https://example.com/story"),
        ]
    )

    assert len(kept) == 1
    assert len(discards) == 1
    assert kept[0].provider == "brave, tavily"
    assert kept[0].providers == ["brave", "tavily"]
    assert kept[0].provider_result_count == 2
    assert set(kept[0].provider_queries) == {"brave", "tavily"}


def test_evidence_dedup_merges_provider_provenance() -> None:
    kept, discards = deduplicate_evidence(
        [
            _evidence("s1", "brave"),
            _evidence("s2", "tavily"),
        ]
    )

    assert len(kept) == 1
    assert len(discards) == 1
    assert kept[0].providers == ["brave", "tavily"]
    assert kept[0].provider_result_count == 2


@pytest.mark.asyncio
async def test_ranker_boosts_multi_provider_sources() -> None:
    ranker = EvidenceRanker(CompositeBoostEmbeddingClient())

    ranked = await ranker.rank(
        _post(),
        [
            _evidence("single", "brave", url="https://example.com/single"),
            _evidence(
                "multi",
                "brave, tavily",
                url="https://example.com/multi",
                providers=["brave", "tavily"],
                provider_result_count=2,
            ),
        ],
    )

    assert ranked[0].id == "multi"
    assert ranked[0].relevance_score > ranked[1].relevance_score


def _search_result(provider: str, url: str) -> SearchResult:
    return SearchResult(
        provider=provider,
        query=f"{provider} query",
        title="Shared story",
        url=url,
        snippet="Snippet",
        rank=1,
    )


def _evidence(
    source_id: str,
    provider: str,
    url: str = "https://example.com/story",
    providers: list[str] | None = None,
    provider_result_count: int = 1,
) -> Evidence:
    return Evidence(
        id=source_id,
        title="Shared story",
        url=url,
        snippet="Snippet",
        content=LONG_CONTENT,
        source_type="web",
        provider=provider,
        providers=providers or [],
        provider_queries={provider: [f"{provider} query"]},
        provider_result_count=provider_result_count,
        query=f"{provider} query",
        canonical_url="https://example.com/story",
        published_at=datetime(2026, 5, 15, tzinfo=UTC),
    )


def _post() -> PostData:
    return PostData(
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        platform="bluesky",
        author=PostAuthor(handle="example.bsky.social"),
        text="Public issue in a shared story.",
        created_at=datetime(2026, 5, 15, tzinfo=UTC),
    )

