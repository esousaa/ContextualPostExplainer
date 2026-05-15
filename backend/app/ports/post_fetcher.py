from typing import Protocol

from app.domain.models import PostData


class PostFetcher(Protocol):
    def can_handle(self, url: str) -> bool: ...

    async def fetch(self, url: str) -> PostData: ...
