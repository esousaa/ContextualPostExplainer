from typing import Protocol

from app.domain.models import PostData


class ImageAnalyzer(Protocol):
    async def analyze(self, post: PostData) -> PostData: ...

