import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from langgraph.graph import END, StateGraph

from app.adapters.eval.fixture_evidence_provider import FixtureEvidenceProvider
from app.adapters.eval.fixture_post_provider import FixturePostProvider
from app.domain.models import EvalCase, Evidence, Explanation, RankedEvidence
from app.domain.validation import CitationValidator
from app.eval.metrics import score_eval_case
from app.graphs.state import ExplanationState
from app.observability.tracing import get_tracer
from app.ports.groundedness_judge import GroundednessJudge
from app.ports.run_recorder import RunRecorder

logger = structlog.get_logger(__name__)

EvalNodeFn = Callable[[ExplanationState], Awaitable[dict[str, object]]]


class EvalExplanationFlow:
    def __init__(
        self,
        post_provider: FixturePostProvider,
        evidence_provider: FixtureEvidenceProvider,
        rank_evidence: Callable[[ExplanationState], Awaitable[list[RankedEvidence]]],
        generate_explanation: Callable[[ExplanationState], Awaitable[Explanation]],
        groundedness_judge: GroundednessJudge | None = None,
        run_recorder: RunRecorder | None = None,
    ) -> None:
        self._post_provider = post_provider
        self._evidence_provider = evidence_provider
        self._rank_evidence = rank_evidence
        self._generate_explanation = generate_explanation
        self._groundedness_judge = groundedness_judge
        self._citation_validator = CitationValidator()
        self._run_recorder = run_recorder
        self._tracer = get_tracer()
        self._graph = self._build_graph()

    async def run_case(self, eval_case: EvalCase) -> ExplanationState:
        state: ExplanationState = {
            "run_id": f"eval_{uuid4().hex}",
            "mode": "eval",
            "case_id": eval_case.id,
            "eval_case": eval_case,
            "started_at": time.perf_counter(),
            "warnings": [],
            "metrics": {},
        }
        return await self._graph.ainvoke(state)

    def _build_graph(self):
        builder = StateGraph(ExplanationState)
        nodes: list[tuple[str, EvalNodeFn]] = [
            ("load_eval_case", self._load_eval_case),
            ("load_fixture_post", self._load_fixture_post),
            ("load_fixture_evidence", self._load_fixture_evidence),
            ("rank_evidence", self._rank_evidence_node),
            ("generate_explanation", self._generate_explanation_node),
            ("validate_citations", self._validate_citations_node),
            ("repair_once_if_needed", self._repair_once_if_needed_node),
            ("judge_groundedness", self._judge_groundedness_node),
            ("score_case", self._score_case),
            ("persist_eval_result", self._persist_eval_result),
        ]
        for node_name, node_fn in nodes:
            builder.add_node(node_name, self._logged_node(node_name, node_fn))

        builder.set_entry_point("load_eval_case")
        for current, next_node in zip(nodes, nodes[1:], strict=False):
            builder.add_edge(current[0], next_node[0])
        builder.add_edge("persist_eval_result", END)
        return builder.compile()

    def _logged_node(self, node_name: str, node_fn: EvalNodeFn) -> EvalNodeFn:
        async def wrapped(state: ExplanationState) -> dict[str, object]:
            started = time.perf_counter()
            event = {"run_id": state["run_id"], "mode": "eval", "node_name": node_name}
            logger.info("node_started", **event)
            if self._run_recorder:
                await self._run_recorder.record_event({"event": "node_started", **event})

            with self._tracer.start_as_current_span(f"eval.{node_name}"):
                result = await node_fn(state)

            duration_ms = int((time.perf_counter() - started) * 1000)
            completed = {**event, "duration_ms": duration_ms}
            logger.info("node_completed", **completed)
            if self._run_recorder:
                await self._run_recorder.record_event({"event": "node_completed", **completed})
            return result

        return wrapped

    async def _load_eval_case(self, state: ExplanationState) -> dict[str, object]:
        return {"case_id": state["eval_case"].id}

    async def _load_fixture_post(self, state: ExplanationState) -> dict[str, object]:
        eval_case = state["eval_case"]
        post = await self._post_provider.fetch_case_post(eval_case.post_fixture)
        return {"post": post}

    async def _load_fixture_evidence(self, state: ExplanationState) -> dict[str, object]:
        eval_case = state["eval_case"]
        evidence = await self._evidence_provider.fetch_case_evidence(eval_case.evidence_fixture)
        return {"evidence": evidence}

    async def _rank_evidence_node(self, state: ExplanationState) -> dict[str, object]:
        return {"ranked_evidence": await self._rank_evidence(state)}

    async def _generate_explanation_node(self, state: ExplanationState) -> dict[str, object]:
        return {"explanation": await self._generate_explanation(state)}

    async def _validate_citations_node(self, state: ExplanationState) -> dict[str, object]:
        validation_warnings = self._citation_validator.validate(
            state["explanation"].bullets,
            list(state.get("ranked_evidence", [])),
        )
        if not validation_warnings:
            return {}
        new_warnings = [
            warning
            for warning in validation_warnings
            if warning not in state["explanation"].warnings
        ]
        if not new_warnings:
            return {}
        explanation = state["explanation"].model_copy(
            update={"warnings": [*state["explanation"].warnings, *new_warnings]}
        )
        return {"explanation": explanation}

    async def _repair_once_if_needed_node(self, _state: ExplanationState) -> dict[str, object]:
        return {}

    async def _judge_groundedness_node(self, state: ExplanationState) -> dict[str, object]:
        if not self._groundedness_judge or not state["explanation"].bullets:
            return {"groundedness_assessments": []}

        sources_by_id = {source.id: source for source in state.get("ranked_evidence", [])}
        assessments = []
        for index, bullet in enumerate(state["explanation"].bullets):
            cited_sources = _cited_sources(bullet.source_ids, sources_by_id)
            assessment = await self._groundedness_judge.judge(index, bullet, cited_sources)
            assessments.append(assessment)
        return {"groundedness_assessments": assessments}

    async def _score_case(self, state: ExplanationState) -> dict[str, object]:
        metrics = score_eval_case(
            state["eval_case"],
            state["explanation"],
            state.get("groundedness_assessments", []),
        )
        return {"eval_metrics": metrics}

    async def _persist_eval_result(self, state: ExplanationState) -> dict[str, object]:
        if self._run_recorder:
            await self._run_recorder.write_run(
                "eval",
                state["run_id"],
                {
                    "case_id": state["eval_case"].id,
                    "metrics": state["eval_metrics"].model_dump(mode="json"),
                    "source_count": len(state.get("ranked_evidence", [])),
                    "groundedness": [
                        item.model_dump(mode="json")
                        for item in state.get("groundedness_assessments", [])
                    ],
                    "warnings": [
                        warning.model_dump(mode="json")
                        for warning in state["explanation"].warnings
                    ],
                    "explanation": state["explanation"].model_dump(mode="json"),
                },
            )
        return {}


def _cited_sources(source_ids: list[str], sources_by_id: dict[str, Evidence]) -> list[Evidence]:
    return [sources_by_id[source_id] for source_id in source_ids if source_id in sources_by_id]
