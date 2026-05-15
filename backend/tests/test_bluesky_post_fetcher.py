import httpx
import pytest
import respx

from app.adapters.bluesky.post_fetcher import PUBLIC_APPVIEW_BASE_URL, BlueskyPostFetcher
from app.domain.errors import PostNotFoundError


@pytest.mark.asyncio
async def test_bluesky_post_fetcher_returns_normalized_post() -> None:
    url = "https://bsky.app/profile/mayor.nyc.gov/post/3mltw7fmlak2y"
    did = "did:plc:mayor"

    with respx.mock:
        respx.get(f"{PUBLIC_APPVIEW_BASE_URL}/xrpc/com.atproto.identity.resolveHandle").respond(
            json={"did": did}
        )
        respx.get(f"{PUBLIC_APPVIEW_BASE_URL}/xrpc/app.bsky.feed.getPostThread").respond(
            json={
                "thread": {
                    "post": {
                        "author": {
                            "handle": "mayor.nyc.gov",
                            "displayName": "Mayor",
                            "did": did,
                        },
                        "record": {
                            "text": "Main post text",
                            "createdAt": "2026-05-14T10:00:00.000Z",
                            "facets": [
                                {
                                    "features": [
                                        {
                                            "$type": "app.bsky.richtext.facet#link",
                                            "uri": "https://example.com/source",
                                        }
                                    ]
                                }
                            ],
                        },
                        "embed": {
                            "images": [
                                {
                                    "fullsize": "https://example.com/image.jpg",
                                    "alt": "Image alt text",
                                }
                            ],
                            "external": {"uri": "https://example.com/source"},
                        },
                    },
                    "parent": {
                        "post": {
                            "record": {
                                "text": "Parent text",
                            }
                        }
                    },
                    "replies": [
                        {
                            "post": {
                                "record": {
                                    "text": "Reply text",
                                }
                            }
                        }
                    ],
                }
            }
        )

        async with httpx.AsyncClient() as client:
            post = await BlueskyPostFetcher(client=client).fetch(url)

    assert post.url.unicode_string() == url
    assert post.platform == "bluesky"
    assert post.author.handle == "mayor.nyc.gov"
    assert post.text == "Main post text"
    assert post.parent_text == "Parent text"
    assert post.thread_text == "Parent text\n\nReply text"
    assert post.images[0].alt_text == "Image alt text"
    assert [link.unicode_string() for link in post.links] == ["https://example.com/source"]


@pytest.mark.asyncio
async def test_bluesky_post_fetcher_maps_404_to_post_not_found() -> None:
    url = "https://bsky.app/profile/mayor.nyc.gov/post/3mltw7fmlak2y"

    with respx.mock:
        respx.get(f"{PUBLIC_APPVIEW_BASE_URL}/xrpc/com.atproto.identity.resolveHandle").respond(
            status_code=404,
            json={"error": "not_found"},
        )

        async with httpx.AsyncClient() as client:
            with pytest.raises(PostNotFoundError):
                await BlueskyPostFetcher(client=client).fetch(url)
