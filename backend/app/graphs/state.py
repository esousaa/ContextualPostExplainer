from typing import Literal, TypedDict

from app.domain.models import (
    EvalCase,
    EvalMetrics,
    Evidence,
    Explanation,
    ExplanationResponse,
    GroundednessAssessment,
    PostData,
    RankedEvidence,
    SearchResult,
)


class ExplanationState(TypedDict, total=False):
    run_id: str
    mode: Literal["live", "eval"]
    input_url: str
    include_debug: bool
    started_at: float
    case_id: str
    post_ref: dict[str, str]
    post: PostData
    thread_sources: list[Evidence]
    image_sources: list[Evidence]
    queries: list[str]
    search_results: list[SearchResult]
    evidence: list[Evidence]
    ranked_evidence: list[RankedEvidence]
    explanation: Explanation
    response: ExplanationResponse
    validation_errors: list[str]
    warnings: list[str]
    metrics: dict[str, object]
    eval_case: EvalCase
    eval_metrics: EvalMetrics
    groundedness_assessments: list[GroundednessAssessment]
