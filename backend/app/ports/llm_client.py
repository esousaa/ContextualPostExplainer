from typing import Protocol

from app.domain.models import Evidence, Explanation, PostData


class LLMClient(Protocol):
    async def decompose_queries(self, post: PostData) -> list[str]: ...

    async def generate_explanation(
        self,
        post: PostData,
        evidence: list[Evidence],
    ) -> Explanation: ...

    async def repair_explanation(
        self,
        post: PostData,
        evidence: list[Evidence],
        invalid_payload: str,
        validation_error: str,
    ) -> Explanation: ...
