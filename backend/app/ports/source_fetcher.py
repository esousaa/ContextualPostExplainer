from typing import Protocol

from app.domain.models import Evidence, SearchResult


class SourceFetcher(Protocol):
    async def fetch(self, result: SearchResult) -> Evidence: ...
