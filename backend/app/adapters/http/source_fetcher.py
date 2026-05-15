from typing import Any

import httpx
import structlog
import trafilatura
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date

from app.application.source_classification import classify_evidence
from app.domain.deduplication import canonicalize_url, stable_source_id
from app.domain.errors import ExternalProviderError
from app.domain.models import Evidence, SearchResult
from app.ports.source_fetcher import SourceFetcher

logger = structlog.get_logger(__name__)


class HttpSourceFetcher(SourceFetcher):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 15.0,
        max_content_chars: int = 4000,
        min_content_chars: int = 200,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_content_chars = max_content_chars
        self._min_content_chars = min_content_chars

    async def fetch(self, result: SearchResult) -> Evidence:
        url = result.url.unicode_string()
        logger.info("source_fetch_started", url=url, provider=result.provider)

        if self._client:
            response = await self._request(self._client, url)
        else:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = await self._request(client, url)

        content = _extract_content(response.text, self._max_content_chars)
        if not content:
            logger.warning("source_fetch_empty_content", url=url)
            raise ExternalProviderError("Source page did not contain extractable text.")
        if len(content) < self._min_content_chars:
            logger.warning("source_fetch_short_content", url=url, content_chars=len(content))
            raise ExternalProviderError("Source page did not contain enough extractable text.")

        final_url = str(response.url.copy_with(fragment=""))
        canonical = canonicalize_url(final_url)
        evidence = classify_evidence(
            Evidence(
                id=stable_source_id(canonical),
                title=result.title,
                url=final_url,
                snippet=result.snippet,
                content=content,
                source_type="web",
                provider=result.provider,
                query=result.query,
                canonical_url=canonical,
                published_at=_extract_published_at(response.text),
            )
        )
        logger.info(
            "source_fetch_completed",
            url=url,
            final_url=final_url,
            content_chars=len(content),
        )
        return evidence

    async def _request(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        try:
            response = await client.get(
                url,
                headers={"User-Agent": "rapidcanvas-contextual-post-explainer/0.1"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "source_fetch_http_error",
                url=url,
                status_code=exc.response.status_code,
            )
            raise ExternalProviderError("Source page returned an HTTP error.") from exc
        except httpx.TimeoutException as exc:
            logger.warning("source_fetch_timeout", url=url)
            raise ExternalProviderError("Source page timed out.") from exc
        except httpx.HTTPError as exc:
            logger.warning("source_fetch_request_failed", url=url, error=str(exc))
            raise ExternalProviderError("Could not fetch source page.") from exc

        return response


async def fetch_source_pages(
    fetcher: SourceFetcher,
    results: list[SearchResult],
) -> tuple[list[Evidence], list[dict[str, Any]]]:
    evidence: list[Evidence] = []
    discards: list[dict[str, Any]] = []

    for result in results:
        try:
            evidence.append(await fetcher.fetch(result))
        except ExternalProviderError as exc:
            discards.append(
                {
                    "url": result.url.unicode_string(),
                    "reason": exc.error_code,
                    "message": exc.message,
                }
            )

    return evidence, discards


def _extract_content(html: str, max_content_chars: int) -> str:
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    content = extracted if extracted else _fallback_extract(html)
    cleaned = " ".join(content.split()) if content else ""
    return cleaned[:max_content_chars]


def _extract_published_at(html: str):
    metadata = trafilatura.extract_metadata(html)
    date_value = getattr(metadata, "date", None) if metadata else None
    if not date_value:
        return None

    try:
        return parse_date(date_value)
    except (TypeError, ValueError, OverflowError):
        return None


def _fallback_extract(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)
