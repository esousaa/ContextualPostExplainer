from pathlib import Path

import pytest

from app.adapters.eval.fixture_evidence_provider import FixtureEvidenceProvider
from app.adapters.eval.fixture_post_provider import FixturePostProvider
from app.application.eval_explanation_service import (
    build_eval_report,
    load_eval_cases,
    persist_eval_report,
)
from app.domain.models import (
    Explanation,
    ExplanationBullet,
    GroundednessAssessment,
    RankedEvidence,
)
from app.eval.metrics import score_eval_case
from app.graphs.eval_graph import EvalExplanationFlow
from app.graphs.state import ExplanationState


@pytest.mark.asyncio
async def test_fixture_providers_load_post_and_evidence() -> None:
    base_dir = Path("../eval")
    cases = load_eval_cases(base_dir / "dataset.yaml")
    post = await FixturePostProvider(base_dir).fetch_case_post(cases[0].post_fixture)
    evidence = await FixtureEvidenceProvider(base_dir).fetch_case_evidence(
        cases[0].evidence_fixture
    )

    assert post.platform == "bluesky"
    assert evidence[0].source_type == "fixture"


@pytest.mark.asyncio
async def test_eval_flow_runs_with_fixtures_and_no_live_providers() -> None:
    base_dir = Path("../eval")
    eval_case = load_eval_cases(base_dir / "dataset.yaml")[0]

    async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
        return [
            RankedEvidence(**source.model_dump(mode="json"), relevance_score=0.8)
            for source in state["evidence"]
        ]

    async def generate_explanation(_state: ExplanationState) -> Explanation:
        return Explanation(
            bullets=[
                ExplanationBullet(text="The post references a public launch.", source_ids=["s1"]),
                ExplanationBullet(text="The cited source explains the launch.", source_ids=["s1"]),
                ExplanationBullet(
                    text="The context is supported by the fixture.",
                    source_ids=["s1"],
                ),
            ],
            confidence="medium",
            warnings=[],
        )

    flow = EvalExplanationFlow(
        post_provider=FixturePostProvider(base_dir),
        evidence_provider=FixtureEvidenceProvider(base_dir),
        rank_evidence=rank_evidence,
        generate_explanation=generate_explanation,
    )

    state = await flow.run_case(eval_case)

    assert state["post"].platform == "bluesky"
    assert state["eval_metrics"].citation_coverage == 1.0
    assert state["eval_metrics"].groundedness is None


@pytest.mark.asyncio
async def test_eval_flow_scores_groundedness_when_judge_is_configured() -> None:
    base_dir = Path("../eval")
    eval_case = load_eval_cases(base_dir / "dataset.yaml")[0]

    async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
        return [
            RankedEvidence(**source.model_dump(mode="json"), relevance_score=0.8)
            for source in state["evidence"]
        ]

    async def generate_explanation(_state: ExplanationState) -> Explanation:
        return Explanation(
            bullets=[
                ExplanationBullet(text="The post references a public launch.", source_ids=["s1"]),
                ExplanationBullet(text="The source only partly supports this.", source_ids=["s1"]),
                ExplanationBullet(text="The source does not support this.", source_ids=["s1"]),
            ],
            confidence="medium",
            warnings=[],
        )

    class FakeGroundednessJudge:
        async def judge(self, bullet_index, bullet, cited_sources):
            verdicts = ["supported", "partially_supported", "unsupported"]
            scores = [1.0, 0.5, 0.0]
            return GroundednessAssessment(
                bullet_index=bullet_index,
                verdict=verdicts[bullet_index],
                score=scores[bullet_index],
                reason=f"judged {bullet.text}",
                source_ids=[source.id for source in cited_sources],
            )

    flow = EvalExplanationFlow(
        post_provider=FixturePostProvider(base_dir),
        evidence_provider=FixtureEvidenceProvider(base_dir),
        rank_evidence=rank_evidence,
        generate_explanation=generate_explanation,
        groundedness_judge=FakeGroundednessJudge(),
    )

    state = await flow.run_case(eval_case)

    assert state["eval_metrics"].groundedness == 0.5
    assert len(state["groundedness_assessments"]) == 3


def test_eval_metrics_scores_citations_and_forbidden_claims() -> None:
    eval_case = load_eval_cases(Path("../eval/dataset.yaml"))[0]
    explanation = Explanation(
        bullets=[
            ExplanationBullet(text=eval_case.must_include_facts[0], source_ids=["s1"]),
            ExplanationBullet(text="Additional cited context.", source_ids=["s1"]),
            ExplanationBullet(text="Another cited point.", source_ids=["s1"]),
        ],
        confidence="medium",
        warnings=[],
    )

    metrics = score_eval_case(
        eval_case,
        explanation,
        [
            GroundednessAssessment(
                bullet_index=0,
                verdict="supported",
                score=1.0,
                reason="supported",
                source_ids=["s1"],
            )
        ],
    )

    assert metrics.fact_coverage is not None
    assert metrics.fact_coverage > 0
    assert metrics.citation_coverage == 1.0
    assert metrics.hallucination_penalty == 0.0
    assert metrics.groundedness == 1.0


def test_build_eval_report_includes_averages() -> None:
    report = build_eval_report(Path("../eval/dataset.yaml"), [])

    assert report["case_count"] == 0
    assert report["averages"]["fact_coverage"] is None


def test_persist_eval_report_writes_json_and_markdown(tmp_path: Path) -> None:
    report = build_eval_report(Path("../eval/dataset.yaml"), [])

    persist_eval_report(report, tmp_path)

    assert (tmp_path / "latest.json").exists()
    assert (tmp_path / "latest.md").exists()
