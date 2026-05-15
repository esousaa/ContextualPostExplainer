from typing import Protocol

from app.domain.models import Evidence, ExplanationBullet, GroundednessAssessment


class GroundednessJudge(Protocol):
    async def judge(
        self,
        bullet_index: int,
        bullet: ExplanationBullet,
        cited_sources: list[Evidence],
    ) -> GroundednessAssessment: ...

