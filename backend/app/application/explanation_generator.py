from app.domain.models import Evidence, Explanation, PostData, RankedEvidence
from app.ports.llm_client import LLMClient


class ExplanationGenerator:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def generate(
        self,
        post: PostData,
        evidence: list[RankedEvidence] | list[Evidence],
    ) -> Explanation:
        if not evidence:
            return Explanation(
                bullets=[],
                confidence="low",
                warnings=[
                    "Insufficient evidence to generate a reliable explanation.",
                    "No explanatory bullets were generated to avoid unsupported claims.",
                ],
            )

        return await self._llm_client.generate_explanation(post, list(evidence))
