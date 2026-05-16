import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.adapters.eval.fixture_evidence_provider import FixtureEvidenceProvider
from app.adapters.eval.fixture_post_provider import FixturePostProvider
from app.adapters.openai.embedding_client import OpenAIEmbeddingClient
from app.adapters.openai.groundedness_judge import OpenAIGroundednessJudge
from app.adapters.openai.llm_client import OpenAILLMClient
from app.application.explanation_generator import ExplanationGenerator
from app.application.ranking import EvidenceRanker
from app.config import Settings
from app.domain.models import EvalCase, Explanation, RankedEvidence
from app.graphs.eval_graph import EvalExplanationFlow
from app.graphs.state import ExplanationState
from app.observability.run_recorder import LocalRunRecorder


class EvalExplanationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run_dataset(self, dataset_path: Path) -> dict[str, Any]:
        cases = load_eval_cases(dataset_path)
        flow = self._build_flow(dataset_path.parent)
        results = [await flow.run_case(eval_case) for eval_case in cases]
        return build_eval_report(dataset_path, results)

    def _build_flow(self, base_dir: Path) -> EvalExplanationFlow:
        llm_client = OpenAILLMClient(
            api_key=self._settings.openai_api_key,
            generation_model=self._settings.openai_generation_model,
        )
        embedding_client = OpenAIEmbeddingClient(
            api_key=self._settings.openai_api_key,
            embedding_model=self._settings.openai_embedding_model,
        )
        ranker = EvidenceRanker(embedding_client)
        generator = ExplanationGenerator(llm_client)
        groundedness_judge = OpenAIGroundednessJudge(
            api_key=self._settings.openai_api_key,
            judge_model=self._settings.openai_judge_model,
        )

        async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
            return await ranker.rank(state["post"], state.get("evidence", []), top_n=8)

        async def generate_explanation(state: ExplanationState) -> Explanation:
            return await generator.generate(state["post"], state.get("ranked_evidence", []))

        return EvalExplanationFlow(
            post_provider=FixturePostProvider(base_dir),
            evidence_provider=FixtureEvidenceProvider(base_dir),
            rank_evidence=rank_evidence,
            generate_explanation=generate_explanation,
            llm_client=llm_client,
            groundedness_judge=groundedness_judge,
            run_recorder=LocalRunRecorder(),
        )


def load_eval_cases(dataset_path: Path) -> list[EvalCase]:
    payload = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    cases = payload["cases"] if isinstance(payload, dict) else payload
    return [EvalCase.model_validate(item) for item in cases]


def build_eval_report(dataset_path: Path, results: list[ExplanationState]) -> dict[str, Any]:
    cases = [_case_result(state) for state in results]
    averages = _averages(cases)
    return {
        "dataset": str(dataset_path),
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(cases),
        "averages": averages,
        "cases": cases,
    }


def persist_eval_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "latest.md").write_text(_markdown_report(report), encoding="utf-8")


def _case_result(state: ExplanationState) -> dict[str, Any]:
    eval_case = state["eval_case"]
    metrics = state["eval_metrics"]
    explanation = state["explanation"]
    return {
        "id": eval_case.id,
        "description": eval_case.description,
        "metrics": metrics.model_dump(mode="json"),
        "bullet_count": len(explanation.bullets),
        "confidence": explanation.confidence,
        "warnings": [warning.model_dump(mode="json") for warning in explanation.warnings],
        "groundedness": [
            item.model_dump(mode="json")
            for item in state.get("groundedness_assessments", [])
        ],
        "source_count": len(state.get("ranked_evidence", [])),
    }


def _averages(cases: list[dict[str, Any]]) -> dict[str, float | None]:
    metric_names = [
        "fact_coverage",
        "citation_coverage",
        "hallucination_penalty",
        "groundedness",
        "usefulness",
    ]
    averages: dict[str, float | None] = {}
    for metric_name in metric_names:
        values = [
            case["metrics"][metric_name]
            for case in cases
            if case["metrics"].get(metric_name) is not None
        ]
        averages[metric_name] = round(sum(values) / len(values), 3) if values else None
    return averages


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Eval Results",
        "",
        f"Dataset: `{report['dataset']}`",
        f"Cases: {report['case_count']}",
        "",
        "| Case | Facts | Cites | Hallucination | Grounded | Useful | Bullets |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for case in report["cases"]:
        metrics = case["metrics"]
        lines.append(
            (
                "| {id} | {fact:.2f} | {cite:.2f} | {halluc:.2f} | "
                "{ground:.2f} | {useful:.2f} | {bullets} |"
            ).format(
                id=case["id"],
                fact=metrics["fact_coverage"] or 0.0,
                cite=metrics["citation_coverage"] or 0.0,
                halluc=metrics["hallucination_penalty"] or 0.0,
                ground=metrics["groundedness"] or 0.0,
                useful=metrics["usefulness"] or 0.0,
                bullets=case["bullet_count"],
            )
        )
    return "\n".join(lines) + "\n"
