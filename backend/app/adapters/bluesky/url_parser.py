from dataclasses import dataclass
from urllib.parse import urlparse

from app.domain.errors import UnsupportedPlatformError


@dataclass(frozen=True)
class BlueskyPostRef:
    handle: str
    rkey: str


def parse_bluesky_post_url(url: str) -> BlueskyPostRef:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.split("/") if part]

    if host != "bsky.app" or len(parts) != 4:
        raise UnsupportedPlatformError("Only public Bluesky post URLs are supported.")

    if parts[0] != "profile" or parts[2] != "post":
        raise UnsupportedPlatformError("Only public Bluesky post URLs are supported.")

    handle = parts[1].strip()
    rkey = parts[3].strip()
    if not handle or not rkey:
        raise UnsupportedPlatformError("Only public Bluesky post URLs are supported.")

    return BlueskyPostRef(handle=handle, rkey=rkey)
