import pytest

from app.adapters.bluesky.url_parser import parse_bluesky_post_url
from app.domain.errors import UnsupportedPlatformError


def test_parse_bluesky_post_url() -> None:
    ref = parse_bluesky_post_url("https://bsky.app/profile/mayor.nyc.gov/post/3mltw7fmlak2y")

    assert ref.handle == "mayor.nyc.gov"
    assert ref.rkey == "3mltw7fmlak2y"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/profile/mayor.nyc.gov/post/3mltw7fmlak2y",
        "https://bsky.app.evil.com/profile/mayor.nyc.gov/post/3mltw7fmlak2y",
        "ftp://bsky.app/profile/mayor.nyc.gov/post/3mltw7fmlak2y",
        "https://bsky.app/profile/mayor.nyc.gov",
        "https://bsky.app/profile/mayor.nyc.gov/feed/3mltw7fmlak2y",
    ],
)
def test_parse_bluesky_post_url_rejects_unsupported_urls(url: str) -> None:
    with pytest.raises(UnsupportedPlatformError):
        parse_bluesky_post_url(url)
