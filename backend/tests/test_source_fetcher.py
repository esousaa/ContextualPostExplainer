import asyncio

import httpx
import pytest
import respx

from app.adapters.http.source_fetcher import HttpSourceFetcher, fetch_source_pages
from app.domain.deduplication import (
    canonicalize_url,
    deduplicate_evidence,
    deduplicate_search_results,
)
from app.domain.errors import ExternalProviderError
from app.domain.models import Evidence, SearchResult


def _search_result(url: str, rank: int = 1, title: str = "Title") -> SearchResult:
    return SearchResult(
        provider="brave",
        query="test query",
        title=title,
        url=url,
        snippet="Snippet",
        rank=rank,
    )


def _evidence(url: str, source_id: str = "src_test") -> Evidence:
    return Evidence(
        id=source_id,
        title="Title",
        url=url,
        snippet="Snippet",
        content="Useful source content with enough detail for downstream citation checks.",
        source_type="web",
    )


def test_canonicalize_url_removes_tracking_and_fragment() -> None:
    assert (
        canonicalize_url("HTTPS://www.Example.com/news/?utm_source=x&b=2&a=1#section")
        == "https://example.com/news?a=1&b=2"
    )


def test_deduplicate_search_results_uses_canonical_url() -> None:
    kept, discards = deduplicate_search_results(
        [
            _search_result("https://www.example.com/news/?utm_source=x", rank=1),
            _search_result("https://example.com/news", rank=2),
        ]
    )

    assert len(kept) == 1
    assert len(discards) == 1
    assert discards[0].reason == "duplicate_canonical_url"


def test_deduplicate_search_results_uses_normalized_title() -> None:
    kept, discards = deduplicate_search_results(
        [
            _search_result("https://example.com/one", rank=1, title="Shared Title"),
            _search_result("https://example.org/two", rank=2, title=" shared   title "),
        ]
    )

    assert len(kept) == 1
    assert discards[0].reason == "duplicate_title"


def test_deduplicate_evidence_uses_content_hash() -> None:
    first = Evidence(
        id="s1",
        title="One",
        url="https://example.com/one",
        snippet="Snippet",
        content="Same content.",
        source_type="web",
    )
    second = Evidence(
        id="s2",
        title="Two",
        url="https://example.com/two",
        snippet="Snippet",
        content="same   content.",
        source_type="web",
    )

    kept, discards = deduplicate_evidence([first, second])

    assert [item.id for item in kept] == ["s1"]
    assert discards[0].reason == "duplicate_content_hash"


@pytest.mark.asyncio
async def test_http_source_fetcher_extracts_clean_content() -> None:
    url = "https://example.com/article"
    html = """
    <html>
      <body>
        <nav>Navigation</nav>
        <article>
          <h1>Article heading</h1>
          <p>This is the main article text with useful context.</p>
        </article>
        <script>ignored()</script>
      </body>
    </html>
    """

    with respx.mock:
        respx.get(url).respond(text=html, headers={"content-type": "text/html"})

        async with httpx.AsyncClient(follow_redirects=True) as client:
            fetcher = HttpSourceFetcher(client=client, min_content_chars=20)
            evidence = await fetcher.fetch(_search_result(url))

    assert evidence.source_type == "web"
    assert evidence.provider == "brave"
    assert evidence.query == "test query"
    assert evidence.canonical_url is not None
    assert evidence.canonical_url.unicode_string() == url
    assert "main article text" in evidence.content
    assert "ignored" not in evidence.content


@pytest.mark.asyncio
async def test_http_source_fetcher_extracts_published_date() -> None:
    url = "https://example.com/article"
    html = """
    <html>
      <head>
        <meta property="article:published_time" content="2026-05-14T12:00:00+00:00">
      </head>
      <body>
        <article>
          <h1>Article heading</h1>
          <p>
            This article has enough useful content to be treated as a citation candidate.
            It includes factual reporting, named entities, a timeline, and additional
            details that the downstream ranker can compare with the source post text.
          </p>
        </article>
      </body>
    </html>
    """

    with respx.mock:
        respx.get(url).respond(text=html, headers={"content-type": "text/html"})

        async with httpx.AsyncClient(follow_redirects=True) as client:
            fetcher = HttpSourceFetcher(client=client)
            evidence = await fetcher.fetch(_search_result(url))

    assert evidence.published_at is not None
    assert evidence.published_at.year == 2026


@pytest.mark.asyncio
async def test_http_source_fetcher_maps_timeout() -> None:
    url = "https://example.com/article"

    with respx.mock:
        respx.get(url).mock(side_effect=httpx.ReadTimeout("timeout"))

        async with httpx.AsyncClient(follow_redirects=True) as client:
            fetcher = HttpSourceFetcher(client=client)

            with pytest.raises(ExternalProviderError):
                await fetcher.fetch(_search_result(url))


@pytest.mark.asyncio
async def test_http_source_fetcher_rejects_empty_content() -> None:
    url = "https://example.com/article"

    with respx.mock:
        respx.get(url).respond(text="<html><body><script>ignored()</script></body></html>")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            fetcher = HttpSourceFetcher(client=client)

            with pytest.raises(ExternalProviderError):
                await fetcher.fetch(_search_result(url))


@pytest.mark.asyncio
async def test_http_source_fetcher_rejects_short_content() -> None:
    url = "https://example.com/article"

    with respx.mock:
        respx.get(url).respond(text="<html><body><p>Short content.</p></body></html>")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            fetcher = HttpSourceFetcher(client=client)

            with pytest.raises(ExternalProviderError):
                await fetcher.fetch(_search_result(url))


@pytest.mark.asyncio
async def test_fetch_source_pages_keeps_successful_sources_when_one_fails() -> None:
    success_url = "https://example.com/good"
    failed_url = "https://example.com/missing"

    with respx.mock:
        respx.get(success_url).respond(text="<html><body><p>Useful content.</p></body></html>")
        respx.get(failed_url).respond(status_code=404)

        async with httpx.AsyncClient(follow_redirects=True) as client:
            fetcher = HttpSourceFetcher(client=client, min_content_chars=10)
            evidence, discards = await fetch_source_pages(
                fetcher,
                [
                    _search_result(success_url, rank=1),
                    _search_result(failed_url, rank=2),
                ],
            )

    assert len(evidence) == 1
    assert len(discards) == 1
    assert discards[0]["url"] == failed_url


@pytest.mark.asyncio
async def test_fetch_source_pages_discards_unexpected_source_errors() -> None:
    class UnexpectedFailureFetcher:
        async def fetch(self, result: SearchResult) -> Evidence:
            if "bad" in result.url.unicode_string():
                raise RuntimeError("parser failed")
            return _evidence(result.url.unicode_string())

    evidence, discards = await fetch_source_pages(
        UnexpectedFailureFetcher(),
        [
            _search_result("https://example.com/good", rank=1),
            _search_result("https://example.com/bad", rank=2),
        ],
    )

    assert len(evidence) == 1
    assert discards == [
        {
            "url": "https://example.com/bad",
            "reason": "unexpected_error",
            "message": "Could not fetch source page.",
        }
    ]


@pytest.mark.asyncio
async def test_fetch_source_pages_limits_concurrent_fetches() -> None:
    class CountingFetcher:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0

        async def fetch(self, result: SearchResult) -> Evidence:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return _evidence(result.url.unicode_string(), source_id=result.url.host or "src")

    fetcher = CountingFetcher()
    results = [_search_result(f"https://example.com/{index}", rank=index + 1) for index in range(8)]

    evidence, discards = await fetch_source_pages(fetcher, results, max_concurrency=3)

    assert len(evidence) == 8
    assert discards == []
    assert fetcher.max_active <= 3
