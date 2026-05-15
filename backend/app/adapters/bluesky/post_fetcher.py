from collections.abc import Mapping
from typing import Any

import httpx
import structlog

from app.adapters.bluesky.url_parser import parse_bluesky_post_url
from app.domain.errors import ExternalProviderError, PostNotFoundError, UnsupportedPlatformError
from app.domain.models import ImageContext, PostAuthor, PostData
from app.ports.post_fetcher import PostFetcher

logger = structlog.get_logger(__name__)

PUBLIC_APPVIEW_BASE_URL = "https://public.api.bsky.app"


class BlueskyPostFetcher(PostFetcher):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        base_url: str = PUBLIC_APPVIEW_BASE_URL,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    def can_handle(self, url: str) -> bool:
        try:
            parse_bluesky_post_url(url)
        except UnsupportedPlatformError:
            return False
        return True

    async def fetch(self, url: str) -> PostData:
        ref = parse_bluesky_post_url(url)
        logger.info("bluesky_fetch_started", handle=ref.handle, rkey=ref.rkey)

        if self._client:
            did = await self._resolve_handle(self._client, ref.handle)
            return await self._fetch_thread(self._client, url, did, ref.rkey)

        async with httpx.AsyncClient(timeout=15.0) as client:
            did = await self._resolve_handle(client, ref.handle)
            return await self._fetch_thread(client, url, did, ref.rkey)

    async def _resolve_handle(self, client: httpx.AsyncClient, handle: str) -> str:
        response = await self._get(
            client,
            "/xrpc/com.atproto.identity.resolveHandle",
            params={"handle": handle},
        )
        did = response.get("did")
        if not isinstance(did, str) or not did:
            raise PostNotFoundError("Could not resolve the Bluesky handle.")
        return did

    async def _fetch_thread(
        self,
        client: httpx.AsyncClient,
        original_url: str,
        did: str,
        rkey: str,
    ) -> PostData:
        uri = f"at://{did}/app.bsky.feed.post/{rkey}"
        response = await self._get(
            client,
            "/xrpc/app.bsky.feed.getPostThread",
            params={"uri": uri, "depth": 3, "parentHeight": 3},
        )

        thread = response.get("thread")
        if not isinstance(thread, Mapping) or "post" not in thread:
            raise PostNotFoundError("Could not fetch the Bluesky post thread.")

        post = _expect_mapping(thread.get("post"), "post")
        record = _expect_mapping(post.get("record"), "record")
        author = _expect_mapping(post.get("author"), "author")

        post_data = PostData(
            url=original_url,
            platform="bluesky",
            author=PostAuthor(
                handle=_string(author.get("handle")),
                display_name=_optional_string(author.get("displayName")),
                did=_optional_string(author.get("did")),
            ),
            text=_string(record.get("text")),
            created_at=_optional_string(record.get("createdAt")),
            images=_extract_images(post),
            links=_extract_links(record, post),
            parent_text=_extract_parent_text(thread),
            quote_text=_extract_quote_text(post),
            thread_text=_extract_thread_text(thread),
        )
        logger.info("bluesky_fetch_completed", handle=post_data.author.handle, rkey=rkey)
        return post_data

    async def _get(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await client.get(f"{self._base_url}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise PostNotFoundError("The Bluesky post was not found.") from exc
            logger.error("bluesky_http_error", status_code=exc.response.status_code)
            raise ExternalProviderError("Bluesky returned an unexpected HTTP error.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("bluesky_request_failed", error=str(exc))
            raise ExternalProviderError("Could not fetch data from Bluesky.") from exc

        if not isinstance(payload, dict):
            raise ExternalProviderError("Bluesky returned an invalid response.")
        return payload


def _expect_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExternalProviderError(f"Bluesky response field is invalid: {field_name}.")
    return value


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _extract_images(post: Mapping[str, Any]) -> list[ImageContext]:
    embed = post.get("embed")
    if not isinstance(embed, Mapping):
        return []

    images = embed.get("images")
    if not isinstance(images, list):
        return []

    contexts: list[ImageContext] = []
    for image in images:
        if not isinstance(image, Mapping):
            continue
        contexts.append(
            ImageContext(
                url=_optional_string(image.get("fullsize")) or _optional_string(image.get("thumb")),
                alt_text=_optional_string(image.get("alt")),
            )
        )
    return contexts


def _extract_links(record: Mapping[str, Any], post: Mapping[str, Any]) -> list[str]:
    links: list[str] = []

    facets = record.get("facets")
    if isinstance(facets, list):
        for facet in facets:
            if not isinstance(facet, Mapping):
                continue
            features = facet.get("features")
            if not isinstance(features, list):
                continue
            for feature in features:
                if isinstance(feature, Mapping):
                    uri = _optional_string(feature.get("uri"))
                    if uri:
                        links.append(uri)

    embed = post.get("embed")
    if isinstance(embed, Mapping):
        external = embed.get("external")
        if isinstance(external, Mapping):
            uri = _optional_string(external.get("uri"))
            if uri:
                links.append(uri)

    return list(dict.fromkeys(links))


def _extract_parent_text(thread: Mapping[str, Any]) -> str | None:
    parent = thread.get("parent")
    if not isinstance(parent, Mapping):
        return None
    post = parent.get("post")
    if not isinstance(post, Mapping):
        return None
    record = post.get("record")
    if not isinstance(record, Mapping):
        return None
    return _optional_string(record.get("text"))


def _extract_quote_text(post: Mapping[str, Any]) -> str | None:
    embed = post.get("embed")
    if not isinstance(embed, Mapping):
        return None

    record_view = embed.get("record")
    if not isinstance(record_view, Mapping):
        return None

    value = record_view.get("value")
    if isinstance(value, Mapping):
        return _optional_string(value.get("text"))

    nested_record = record_view.get("record")
    if isinstance(nested_record, Mapping):
        nested_value = nested_record.get("value")
        if isinstance(nested_value, Mapping):
            return _optional_string(nested_value.get("text"))

    return None


def _extract_thread_text(thread: Mapping[str, Any]) -> str | None:
    texts: list[str] = []

    parent_text = _extract_parent_text(thread)
    if parent_text:
        texts.append(parent_text)

    replies = thread.get("replies")
    if isinstance(replies, list):
        for reply in replies[:5]:
            if not isinstance(reply, Mapping):
                continue
            post = reply.get("post")
            if not isinstance(post, Mapping):
                continue
            record = post.get("record")
            if isinstance(record, Mapping):
                text = _optional_string(record.get("text"))
                if text:
                    texts.append(text)

    return "\n\n".join(texts) if texts else None
