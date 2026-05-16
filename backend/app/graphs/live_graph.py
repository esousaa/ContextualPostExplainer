import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog
from langgraph.graph import END, StateGraph

from app.adapters.bluesky.url_parser import parse_bluesky_post_url
from app.adapters.http.source_fetcher import fetch_source_pages
from app.application.image_evidence_builder import build_image_evidence
from app.application.provider_diagnostics import (
    multi_provider_source_count,
    provider_counts_for_sources,
    search_provider_diagnostics,
)
from app.application.query_planning import augment_live_queries
from app.application.source_classification import classify_evidence
from app.application.source_quality import evaluate_source_quality
from app.config import Settings
from app.domain.deduplication import deduplicate_evidence, deduplicate_search_results
from app.domain.errors import DomainError
from app.domain.models import (
    Evidence,
    Explanation,
    ExplanationResponse,
    RankedEvidence,
    SearchResult,
)
from app.domain.validation import CitationValidator
from app.graphs.citation_repair import (
    repair_citation_contract_once,
    validate_citation_contract,
)
from app.graphs.state import ExplanationState
from app.observability.tracing import get_tracer
from app.ports.image_analyzer import ImageAnalyzer
from app.ports.llm_client import LLMClient
from app.ports.post_fetcher import PostFetcher
from app.ports.run_recorder import RunRecorder
from app.ports.search_provider import SearchProvider
from app.ports.source_fetcher import SourceFetcher

logger = structlog.get_logger(__name__)

NodeFn = Callable[[ExplanationState], Awaitable[dict[str, object]]]
ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]
PROMPT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "prompts" / "prompts.toml"

LIVE_NODE_STEPS = {
    "validate_live_config": "Fetching post",
    "parse_post_url": "Fetching post",
    "fetch_bluesky_post_thread": "Fetching post",
    "analyze_images_optional": "Analyzing media",
    "decompose_queries": "Searching context",
    "search_web_context": "Searching context",
    "fetch_source_pages": "Reading sources",
    "rank_evidence": "Ranking evidence",
    "generate_explanation": "Generating explanation",
    "validate_citations": "Generating explanation",
    "repair_once_if_needed": "Generating explanation",
    "finalize_response": "Generating explanation",
}

LIVE_NODE_ORDER = tuple(LIVE_NODE_STEPS)


class LiveExplanationFlow:
    def __init__(
        self,
        settings: Settings,
        post_fetcher: PostFetcher,
        search_provider: SearchProvider,
        source_fetcher: SourceFetcher,
        llm_client: LLMClient,
        rank_evidence: Callable[
            [ExplanationState],
            Awaitable[list[RankedEvidence]],
        ],
        generate_explanation: Callable[
            [ExplanationState],
            Awaitable[Explanation],
        ],
        image_analyzer: ImageAnalyzer | None = None,
        run_recorder: RunRecorder | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self._settings = settings
        self._post_fetcher = post_fetcher
        self._search_provider = search_provider
        self._source_fetcher = source_fetcher
        self._llm_client = llm_client
        self._rank_evidence = rank_evidence
        self._generate_explanation = generate_explanation
        self._image_analyzer = image_analyzer
        self._citation_validator = CitationValidator()
        self._run_recorder = run_recorder
        self._progress_callback = progress_callback
        self._tracer = get_tracer()
        self._graph = self._build_graph()

    async def run(self, url: str, include_debug: bool = False) -> ExplanationResponse:
        state: ExplanationState = {
            "run_id": f"run_{uuid4().hex}",
            "mode": "live",
            "input_url": url,
            "include_debug": include_debug,
            "started_at": time.perf_counter(),
            "warnings": [],
            "metrics": {},
        }
        await self._emit_progress(
            {
                "type": "run_started",
                "run_id": state["run_id"],
                "status": "active",
                "node_name": None,
                "step": "Fetching post",
                "message": "Live analysis started.",
            }
        )
        try:
            result = await self._graph.ainvoke(state)
        except Exception as exc:
            await self._record_failed_run(state, exc)
            raise
        await self._record_completed_run(result)
        return result["response"]

    def _build_graph(self):
        builder = StateGraph(ExplanationState)
        nodes: list[tuple[str, NodeFn]] = [
            ("validate_live_config", self._validate_live_config),
            ("parse_post_url", self._parse_post_url),
            ("fetch_bluesky_post_thread", self._fetch_bluesky_post_thread),
            ("analyze_images_optional", self._analyze_images_optional),
            ("decompose_queries", self._decompose_queries),
            ("search_web_context", self._search_web_context),
            ("fetch_source_pages", self._fetch_source_pages),
            ("rank_evidence", self._rank_evidence_node),
            ("generate_explanation", self._generate_explanation_node),
            ("validate_citations", self._validate_citations_node),
            ("repair_once_if_needed", self._repair_once_if_needed_node),
            ("finalize_response", self._finalize_response),
        ]

        for node_name, node_fn in nodes:
            builder.add_node(node_name, self._logged_node(node_name, node_fn))

        builder.set_entry_point("validate_live_config")
        for current, next_node in zip(nodes, nodes[1:], strict=False):
            builder.add_edge(current[0], next_node[0])
        builder.add_edge("finalize_response", END)
        return builder.compile()

    def _logged_node(self, node_name: str, node_fn: NodeFn) -> NodeFn:
        async def wrapped(state: ExplanationState) -> dict[str, object]:
            started = time.perf_counter()
            event = {"run_id": state["run_id"], "mode": "live", "node_name": node_name}
            logger.info("node_started", **event)
            if self._run_recorder:
                await self._run_recorder.record_event({"event": "node_started", **event})
            await self._emit_node_progress("node_started", event, "active")

            with self._tracer.start_as_current_span(f"live.{node_name}"):
                result = await node_fn(state)

            duration_ms = int((time.perf_counter() - started) * 1000)
            completed = {**event, "duration_ms": duration_ms}
            logger.info("node_completed", **completed)
            if self._run_recorder:
                await self._run_recorder.record_event({"event": "node_completed", **completed})
            await self._emit_node_progress(
                "node_completed",
                completed,
                _completed_node_status(node_name),
            )
            return result

        return wrapped

    async def _emit_node_progress(
        self,
        event_type: str,
        event: dict[str, object],
        status: str,
    ) -> None:
        node_name = str(event["node_name"])
        step = LIVE_NODE_STEPS[node_name]
        payload = {
            "type": event_type,
            "run_id": event["run_id"],
            "status": status,
            "node_name": node_name,
            "step": step,
            "message": _progress_message(step, event_type, status),
        }
        if "duration_ms" in event:
            payload["duration_ms"] = event["duration_ms"]
        await self._emit_progress(payload)

    async def _emit_progress(self, payload: dict[str, Any]) -> None:
        if not self._progress_callback:
            return
        await self._progress_callback(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                **payload,
            }
        )

    async def _validate_live_config(self, _state: ExplanationState) -> dict[str, object]:
        self._settings.require_live_search_provider()
        return {}

    async def _parse_post_url(self, state: ExplanationState) -> dict[str, object]:
        ref = parse_bluesky_post_url(state["input_url"])
        return {"post_ref": {"handle": ref.handle, "rkey": ref.rkey}}

    async def _fetch_bluesky_post_thread(self, state: ExplanationState) -> dict[str, object]:
        post = await self._post_fetcher.fetch(state["input_url"])
        return {
            "post": post,
            "thread_sources": _thread_evidence_sources(post),
        }

    async def _analyze_images_optional(self, state: ExplanationState) -> dict[str, object]:
        post = state["post"]
        if not post.images:
            return {}
        metrics = {
            **state.get("metrics", {}),
            "image_count": len(post.images),
            "image_analysis_enabled": self._image_analyzer is not None,
        }
        if not self._image_analyzer:
            return {
                "image_sources": build_image_evidence(post),
                "metrics": metrics,
                "warnings": [*state.get("warnings", []), "Image analysis is not enabled."],
            }
        try:
            analyzed_post = await self._image_analyzer.analyze(post)
        except Exception:
            logger.warning("image_analysis_failed", run_id=state["run_id"])
            return {
                "image_sources": build_image_evidence(post),
                "metrics": {**metrics, "image_analysis_failed": True},
                "warnings": [*state.get("warnings", []), "Image analysis failed."],
            }

        image_sources = build_image_evidence(analyzed_post)
        return {
            "post": analyzed_post,
            "image_sources": image_sources,
            "metrics": {**metrics, "image_evidence_count": len(image_sources)},
        }

    async def _decompose_queries(self, state: ExplanationState) -> dict[str, object]:
        llm_queries = await self._llm_client.decompose_queries(state["post"])
        queries = augment_live_queries(state["post"], llm_queries)
        return {"queries": queries}

    async def _search_web_context(self, state: ExplanationState) -> dict[str, object]:
        results: list[SearchResult] = []
        for query in state["queries"]:
            results.extend(await self._search_provider.search(query, max_results=5))

        kept, discards = deduplicate_search_results(results)
        metrics = {
            **state.get("metrics", {}),
            "search_results_received": len(results),
            "search_results_by_provider": _provider_counts(results),
            **search_provider_diagnostics(results),
            "search_results_discarded": [discard.__dict__ for discard in discards],
        }
        return {"search_results": kept, "metrics": metrics}

    async def _fetch_source_pages(self, state: ExplanationState) -> dict[str, object]:
        web_evidence, fetch_discards = await fetch_source_pages(
            self._source_fetcher,
            state.get("search_results", [])[:12],
        )
        kept, dedup_discards = deduplicate_evidence(web_evidence)
        metrics = {
            **state.get("metrics", {}),
            "source_fetch_discards": fetch_discards,
            "evidence_discarded": [discard.__dict__ for discard in dedup_discards],
        }
        context_sources = [*state.get("thread_sources", []), *state.get("image_sources", [])]
        evidence = [*context_sources, *kept] if kept else []
        return {"evidence": evidence, "metrics": metrics}

    async def _rank_evidence_node(self, state: ExplanationState) -> dict[str, object]:
        ranked = await self._rank_evidence(state)
        ranked_ids = {item.id for item in ranked}
        ranking_discards = [
            {
                "id": item.id,
                "title": item.title,
                "url": item.url.unicode_string() if item.url else None,
                "reason": _ranking_discard_reason(state, item),
            }
            for item in state.get("evidence", [])
            if item.id not in ranked_ids and item.source_type == "web"
        ]
        metrics = {
            **state.get("metrics", {}),
            "ranking_discards": ranking_discards,
            "ranked_sources_by_provider": provider_counts_for_sources(ranked),
            "ranked_multi_provider_source_count": multi_provider_source_count(ranked),
        }
        return {"ranked_evidence": ranked, "metrics": metrics}

    async def _generate_explanation_node(self, state: ExplanationState) -> dict[str, object]:
        explanation = await self._generate_explanation(state)
        return {"explanation": explanation}

    async def _validate_citations_node(self, state: ExplanationState) -> dict[str, object]:
        result = validate_citation_contract(
            state["explanation"],
            list(state.get("ranked_evidence", [])),
            self._citation_validator,
        )
        metrics = {
            **state.get("metrics", {}),
            "citation_repair_needed": bool(result.get("needs_repair")),
        }
        return {**result, "metrics": metrics}

    async def _repair_once_if_needed_node(self, state: ExplanationState) -> dict[str, object]:
        result = await repair_citation_contract_once(
            post=state["post"],
            evidence=list(state.get("ranked_evidence", [])),
            explanation=state["explanation"],
            validation_error=state.get("validation_error"),
            validation_warnings=list(state.get("validation_warnings", [])),
            llm_client=self._llm_client,
            citation_validator=self._citation_validator,
        )
        if not result:
            return {}
        metrics = {
            **state.get("metrics", {}),
            "citation_repair_attempted": True,
            "citation_repair_left_bullets": bool(result["explanation"].bullets),
        }
        return {**result, "metrics": metrics}

    async def _finalize_response(self, state: ExplanationState) -> dict[str, object]:
        explanation = state["explanation"]
        execution_time_ms = int((time.perf_counter() - state["started_at"]) * 1000)
        ranked_sources = list(state.get("ranked_evidence", []))
        cited_sources = _cited_sources(explanation, ranked_sources)
        response = ExplanationResponse(
            post=state["post"],
            explanation=explanation.bullets,
            sources=cited_sources,
            confidence=explanation.confidence,
            warnings=[*state.get("warnings", []), *explanation.warnings],
            execution_time_ms=execution_time_ms,
        )
        return {"response": response}

    async def _record_completed_run(self, state: ExplanationState) -> None:
        if self._run_recorder:
            response = state["response"]
            ranked_sources = list(state.get("ranked_evidence", []))
            cited_sources = _cited_sources(state["explanation"], ranked_sources)
            config = _config_snapshot(self._settings)
            metrics = {
                **state.get("metrics", {}),
                "cited_sources_by_provider": provider_counts_for_sources(cited_sources),
                "cited_multi_provider_source_count": multi_provider_source_count(cited_sources),
            }
            await self._run_recorder.write_run(
                "live",
                state["run_id"],
                {
                    "input_url": state["input_url"],
                    "status": "completed" if response.explanation else "no_explanation",
                    **config,
                    "config": config,
                    "queries": state.get("queries", []),
                    "metrics": metrics,
                    "sources": [source.model_dump(mode="json") for source in ranked_sources],
                    "cited_sources": [source.model_dump(mode="json") for source in cited_sources],
                    "warnings": [warning.model_dump(mode="json") for warning in response.warnings],
                    "response": response.model_dump(mode="json"),
                },
            )

    async def _record_failed_run(self, state: ExplanationState, exc: Exception) -> None:
        if not self._run_recorder:
            return

        config = _config_snapshot(self._settings)
        await self._run_recorder.write_run(
            "live",
            state["run_id"],
            {
                "input_url": state["input_url"],
                "status": "failed",
                **config,
                "config": config,
                "queries": state.get("queries", []),
                "metrics": state.get("metrics", {}),
                "warnings": _warning_payloads(state.get("warnings", [])),
                "error": _error_payload(exc),
            },
        )


def _thread_evidence_sources(post) -> list[Evidence]:
    sources = [
        classify_evidence(
            Evidence(
                id="thread_original",
                title=f"Bluesky post by @{post.author.handle}",
                url=post.url,
                snippet=post.text[:300],
                content=post.text,
                source_type="thread",
                provider="bluesky",
                publisher=post.author.handle,
            )
        )
    ]

    context_parts = [post.parent_text, post.quote_text, post.thread_text]
    context = "\n\n".join(part for part in context_parts if part)
    if context:
        sources.append(
            classify_evidence(
                Evidence(
                    id="thread_context",
                    title=f"Bluesky thread context for @{post.author.handle}",
                    url=post.url,
                    snippet=context[:300],
                    content=context,
                    source_type="social",
                    provider="bluesky",
                    publisher=post.author.handle,
                )
            )
        )

    return sources


def _ranking_discard_reason(state: ExplanationState, evidence: Evidence) -> str:
    quality = evaluate_source_quality(state["post"], evidence)
    return quality.reason or "ranked_below_selected_sources"


def _cited_sources(
    explanation: Explanation,
    ranked_sources: list[RankedEvidence],
) -> list[RankedEvidence]:
    cited_ids = {source_id for bullet in explanation.bullets for source_id in bullet.source_ids}
    return [source for source in ranked_sources if source.id in cited_ids]


def _provider_counts(results: list[SearchResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.provider] = counts.get(result.provider, 0) + 1
    return counts


def _completed_node_status(node_name: str) -> str:
    node_index = LIVE_NODE_ORDER.index(node_name)
    next_index = node_index + 1
    if next_index >= len(LIVE_NODE_ORDER):
        return "completed"

    current_step = LIVE_NODE_STEPS[node_name]
    next_step = LIVE_NODE_STEPS[LIVE_NODE_ORDER[next_index]]
    return "completed" if current_step != next_step else "active"


def _progress_message(step: str, event_type: str, status: str) -> str:
    if event_type == "node_started":
        return f"{step} started."
    if status == "completed":
        return f"{step} completed."
    return f"{step} is still running."


def _error_payload(exc: Exception) -> dict[str, object]:
    if isinstance(exc, DomainError):
        return {
            "error": exc.error_code,
            "message": exc.message,
            "status": int(exc.status_code),
        }
    return {
        "error": "unexpected_error",
        "message": str(exc),
        "status": 500,
    }


def _warning_payloads(warnings: list[object]) -> list[object]:
    payloads: list[object] = []
    for warning in warnings:
        if hasattr(warning, "model_dump"):
            payloads.append(warning.model_dump(mode="json"))
        else:
            payloads.append(warning)
    return payloads


def _config_snapshot(settings: Settings) -> dict[str, object]:
    search_provider = settings.search_provider
    generation_model = settings.openai_generation_model
    judge_model = settings.openai_judge_model
    embedding_model = settings.openai_embedding_model
    vision_model = settings.openai_vision_model
    comparison_config_id = settings.comparison_config_id or _comparison_config_id(
        search_provider=search_provider,
        generation_model=generation_model,
        judge_model=judge_model,
        embedding_model=embedding_model,
        vision_model=vision_model,
    )

    return {
        "search_provider": search_provider,
        "openai_generation_model": generation_model,
        "openai_judge_model": judge_model,
        "openai_embedding_model": embedding_model,
        "openai_vision_model": vision_model,
        "prompt_config_path": "app/prompts/prompts.toml",
        "prompt_config_hash": _prompt_config_hash(),
        "comparison_group_id": settings.comparison_group_id or "manual_live",
        "comparison_config_id": comparison_config_id,
    }


def _comparison_config_id(
    search_provider: str | None,
    generation_model: str,
    judge_model: str,
    embedding_model: str,
    vision_model: str | None,
) -> str:
    parts = [
        search_provider or "no_search",
        f"gen_{generation_model}",
        f"judge_{judge_model}",
        f"embed_{embedding_model}",
        f"vision_{vision_model or 'none'}",
    ]
    return "__".join(_slug(part) for part in parts)


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value).strip("_")


def _prompt_config_hash() -> str | None:
    try:
        return sha256(PROMPT_CONFIG_PATH.read_bytes()).hexdigest()
    except OSError:
        return None
