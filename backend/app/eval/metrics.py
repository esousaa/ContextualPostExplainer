from app.domain.models import EvalCase, EvalMetrics, Explanation, GroundednessAssessment
from app.eval.groundedness import groundedness_score


def score_eval_case(
    eval_case: EvalCase,
    explanation: Explanation,
    groundedness: list[GroundednessAssessment] | None = None,
) -> EvalMetrics:
    text = " ".join(bullet.text for bullet in explanation.bullets)
    fact_coverage = _coverage(eval_case.must_include_facts, text)
    hallucination_penalty = _forbidden_coverage(eval_case.must_not_claim, text)
    citation_coverage = _citation_coverage(explanation)
    groundedness_metric = groundedness_score(groundedness or [])
    usefulness = _usefulness(
        fact_coverage,
        citation_coverage,
        hallucination_penalty,
        groundedness_metric,
    )

    if not explanation.bullets and eval_case.minimum_sources == 0:
        usefulness = 3.0

    return EvalMetrics(
        fact_coverage=fact_coverage,
        citation_coverage=citation_coverage,
        hallucination_penalty=hallucination_penalty,
        groundedness=groundedness_metric,
        usefulness=usefulness,
    )


def _coverage(expected: list[str], text: str) -> float:
    if not expected:
        return 1.0

    normalized_text = text.casefold()
    hits = 0
    for item in expected:
        if item.casefold() in normalized_text or _token_overlap(item, normalized_text) >= 0.5:
            hits += 1

    return hits / len(expected)


def _forbidden_coverage(forbidden: list[str], text: str) -> float:
    if not forbidden:
        return 0.0

    normalized_text = text.casefold()
    hits = 0
    for item in forbidden:
        if item.casefold() in normalized_text or _token_overlap(item, normalized_text) >= 0.8:
            hits += 1

    return hits / len(forbidden)


def _citation_coverage(explanation: Explanation) -> float:
    if not explanation.bullets:
        return 1.0

    cited = sum(1 for bullet in explanation.bullets if bullet.source_ids)
    return cited / len(explanation.bullets)


def _usefulness(
    fact_coverage: float,
    citation_coverage: float,
    hallucination_penalty: float,
    groundedness: float | None,
) -> float:
    if groundedness is None:
        score = (
            1.0
            + (fact_coverage * 2.5)
            + (citation_coverage * 1.5)
            - (hallucination_penalty * 2.0)
        )
        return max(1.0, min(5.0, round(score, 2)))

    groundedness_component = 0.0 if groundedness is None else groundedness * 1.0
    score = (
        1.0
        + (fact_coverage * 2.0)
        + (citation_coverage * 1.0)
        + groundedness_component
        - (hallucination_penalty * 2.0)
    )
    return max(1.0, min(5.0, round(score, 2)))


def _token_overlap(expected: str, actual: str) -> float:
    expected_tokens = {token for token in expected.casefold().split() if len(token) > 3}
    if not expected_tokens:
        return 0.0

    actual_tokens = {token for token in actual.split() if len(token) > 3}
    return len(expected_tokens & actual_tokens) / len(expected_tokens)
