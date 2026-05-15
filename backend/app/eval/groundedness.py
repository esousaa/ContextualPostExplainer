from app.domain.models import GroundednessAssessment

VERDICT_SCORES = {
    "supported": 1.0,
    "partially_supported": 0.5,
    "unsupported": 0.0,
}


def groundedness_score(assessments: list[GroundednessAssessment]) -> float | None:
    if not assessments:
        return None
    return round(sum(item.score for item in assessments) / len(assessments), 3)


def score_for_verdict(verdict: str) -> float:
    return VERDICT_SCORES.get(verdict, 0.0)

