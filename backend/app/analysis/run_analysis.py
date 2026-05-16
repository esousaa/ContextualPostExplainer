import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Literal

from pydantic import BaseModel, Field

AnalysisRunStatus = Literal["completed", "no_explanation", "failed", "unknown"]


class AnalysisRunMetrics(BaseModel):
    run_id: str
    url: str | None = None
    generated_at: str | None = None
    status: AnalysisRunStatus
    confidence: str | None = None
    search_provider: str | None = None
    generation_model: str | None = None
    judge_model: str | None = None
    embedding_model: str | None = None
    vision_model: str | None = None
    comparison_group_id: str | None = None
    comparison_config_id: str | None = None
    bullet_count: int = Field(ge=0)
    cited_source_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    execution_time_ms: int | None = None
    search_results_received: int | None = None
    search_provider_overlap_count: int | None = None
    ranked_multi_provider_source_count: int | None = None
    cited_multi_provider_source_count: int | None = None
    search_time_ms: int | None = None
    fetch_time_ms: int | None = None


class AnalysisAggregate(BaseModel):
    key: str
    run_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    no_explanation_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    avg_execution_time_ms: float | None = None
    avg_bullet_count: float | None = None
    avg_cited_source_count: float | None = None
    avg_warning_count: float | None = None
    avg_search_results_received: float | None = None
    avg_search_provider_overlap_count: float | None = None
    avg_search_time_ms: float | None = None
    avg_fetch_time_ms: float | None = None


class UrlBehaviorComparison(BaseModel):
    url: str
    run_count: int = Field(ge=0)
    behavior_changed: bool
    latest_status: AnalysisRunStatus
    latest_confidence: str | None = None
    latest_bullet_count: int = Field(ge=0)
    bullet_counts: list[int]
    confidence_values: list[str]
    status_values: list[AnalysisRunStatus]
    runs: list[AnalysisRunMetrics]


class AnalysisOverview(BaseModel):
    total_runs: int = Field(ge=0)
    total_urls: int = Field(ge=0)
    provider_aggregates: list[AnalysisAggregate]
    llm_aggregates: list[AnalysisAggregate]
    url_comparisons: list[UrlBehaviorComparison]


class LocalAnalysisStore:
    def __init__(self, base_dir: Path = Path("runs")) -> None:
        self._base_dir = base_dir

    def overview(self, limit: int = 200) -> AnalysisOverview:
        runs = self._runs(limit=limit)
        return AnalysisOverview(
            total_runs=len(runs),
            total_urls=len({run.url for run in runs if run.url}),
            provider_aggregates=_aggregates(
                runs,
                key_for_run=lambda run: run.search_provider or "unknown_provider",
            ),
            llm_aggregates=_aggregates(
                runs,
                key_for_run=lambda run: _llm_key(run),
            ),
            url_comparisons=_url_comparisons(runs),
        )

    def _runs(self, limit: int) -> list[AnalysisRunMetrics]:
        documents = [_load_json(path) for path in self._run_paths()]
        runs = [_run_metrics(document) for document in documents if document]
        runs.sort(key=lambda item: item.generated_at or "", reverse=True)
        return _latest_comparable_runs(runs)[:limit]

    def _run_paths(self) -> list[Path]:
        directory = self._base_dir / "live"
        if not directory.exists():
            return []
        return list(directory.glob("*.json"))


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _latest_comparable_runs(runs: list[AnalysisRunMetrics]) -> list[AnalysisRunMetrics]:
    latest: list[AnalysisRunMetrics] = []
    seen: set[tuple[str, str, str, str]] = set()
    for run in runs:
        key = _comparison_key(run)
        if key in seen:
            continue
        seen.add(key)
        latest.append(run)
    return latest


def _comparison_key(run: AnalysisRunMetrics) -> tuple[str, str, str, str]:
    if run.comparison_group_id and run.comparison_config_id and run.url:
        return (
            "comparison",
            run.comparison_group_id,
            run.comparison_config_id,
            run.url,
        )
    return ("run", run.run_id, "", "")


def _run_metrics(document: dict[str, Any]) -> AnalysisRunMetrics:
    response = document.get("response") or {}
    metrics = document.get("metrics") or {}
    explanation = response.get("explanation") or []
    cited_sources = document.get("cited_sources") or response.get("sources") or []
    sources = document.get("sources") or cited_sources
    warnings = document.get("warnings") or response.get("warnings") or []
    config = _config(document)

    return AnalysisRunMetrics(
        run_id=str(document["run_id"]),
        url=document.get("input_url") or _post_url(response),
        generated_at=document.get("generated_at"),
        status=_status(document),
        confidence=response.get("confidence"),
        search_provider=_search_provider(document, metrics, config),
        generation_model=_string_config(
            document,
            config,
            "openai_generation_model",
        ),
        judge_model=_string_config(
            document,
            config,
            "openai_judge_model",
        ),
        embedding_model=_string_config(
            document,
            config,
            "openai_embedding_model",
        ),
        vision_model=_string_config(
            document,
            config,
            "openai_vision_model",
        ),
        comparison_group_id=_string_config(document, config, "comparison_group_id"),
        comparison_config_id=_string_config(document, config, "comparison_config_id"),
        bullet_count=len(explanation),
        cited_source_count=len(cited_sources),
        source_count=len(sources),
        warning_count=len(warnings),
        execution_time_ms=response.get("execution_time_ms"),
        search_results_received=_int_metric(metrics, "search_results_received"),
        search_provider_overlap_count=_int_metric(metrics, "search_provider_overlap_count"),
        ranked_multi_provider_source_count=_int_metric(
            metrics,
            "ranked_multi_provider_source_count",
        ),
        cited_multi_provider_source_count=_int_metric(
            metrics,
            "cited_multi_provider_source_count",
        ),
        search_time_ms=_node_duration(document, "search_web_context"),
        fetch_time_ms=_node_duration(document, "fetch_source_pages"),
    )


def _config(document: dict[str, Any]) -> dict[str, Any]:
    config = document.get("config")
    return config if isinstance(config, dict) else {}


def _post_url(response: dict[str, Any]) -> str | None:
    post = response.get("post")
    if not isinstance(post, dict):
        return None
    url = post.get("url")
    return url if isinstance(url, str) else None


def _status(document: dict[str, Any]) -> AnalysisRunStatus:
    if document.get("status") == "failed" or document.get("error"):
        return "failed"
    response = document.get("response") or {}
    if response and not response.get("explanation"):
        return "no_explanation"
    if response:
        return "completed"
    return "unknown"


def _search_provider(
    document: dict[str, Any],
    metrics: dict[str, Any],
    config: dict[str, Any],
) -> str | None:
    configured = _string_config(document, config, "search_provider")
    if configured:
        return configured

    provider_counts = metrics.get("search_results_by_provider")
    if not isinstance(provider_counts, dict):
        return None

    providers = sorted(str(provider) for provider in provider_counts)
    if len(providers) > 1:
        return "composite"
    return providers[0] if providers else None


def _string_config(
    document: dict[str, Any],
    config: dict[str, Any],
    field: str,
) -> str | None:
    value = document.get(field) if document.get(field) is not None else config.get(field)
    return value if isinstance(value, str) and value.strip() else None


def _int_metric(metrics: dict[str, Any], field: str) -> int | None:
    value = metrics.get(field)
    return value if isinstance(value, int) else None


def _node_duration(document: dict[str, Any], node_name: str) -> int | None:
    for event in document.get("events", []):
        if event.get("event") != "node_completed":
            continue
        if event.get("node_name") != node_name:
            continue
        duration = event.get("duration_ms")
        return duration if isinstance(duration, int) else None
    return None


def _aggregates(
    runs: list[AnalysisRunMetrics],
    key_for_run,
) -> list[AnalysisAggregate]:
    grouped: dict[str, list[AnalysisRunMetrics]] = defaultdict(list)
    for run in runs:
        grouped[key_for_run(run)].append(run)

    aggregates = [_aggregate(key, items) for key, items in grouped.items()]
    aggregates.sort(key=lambda item: item.run_count, reverse=True)
    return aggregates


def _aggregate(key: str, runs: list[AnalysisRunMetrics]) -> AnalysisAggregate:
    status_counts = Counter(run.status for run in runs)
    return AnalysisAggregate(
        key=key,
        run_count=len(runs),
        completed_count=status_counts["completed"],
        no_explanation_count=status_counts["no_explanation"],
        failed_count=status_counts["failed"],
        avg_execution_time_ms=_average(run.execution_time_ms for run in runs),
        avg_bullet_count=_average(run.bullet_count for run in runs),
        avg_cited_source_count=_average(run.cited_source_count for run in runs),
        avg_warning_count=_average(run.warning_count for run in runs),
        avg_search_results_received=_average(run.search_results_received for run in runs),
        avg_search_provider_overlap_count=_average(
            run.search_provider_overlap_count for run in runs
        ),
        avg_search_time_ms=_average(run.search_time_ms for run in runs),
        avg_fetch_time_ms=_average(run.fetch_time_ms for run in runs),
    )


def _average(values) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    return round(mean(numbers), 2) if numbers else None


def _llm_key(run: AnalysisRunMetrics) -> str:
    parts = [
        f"gen={run.generation_model or 'unknown'}",
        f"judge={run.judge_model or 'unknown'}",
        f"embed={run.embedding_model or 'unknown'}",
        f"vision={run.vision_model or 'unknown'}",
    ]
    return " | ".join(parts)


def _url_comparisons(runs: list[AnalysisRunMetrics]) -> list[UrlBehaviorComparison]:
    grouped: dict[str, list[AnalysisRunMetrics]] = defaultdict(list)
    for run in runs:
        if run.url:
            grouped[run.url].append(run)

    comparisons = [_url_comparison(url, items) for url, items in grouped.items()]
    comparisons.sort(key=lambda item: (not item.behavior_changed, item.url))
    return comparisons


def _url_comparison(
    url: str,
    runs: list[AnalysisRunMetrics],
) -> UrlBehaviorComparison:
    ordered = sorted(runs, key=lambda item: item.generated_at or "", reverse=True)
    latest = ordered[0]
    bullet_counts = sorted({run.bullet_count for run in runs})
    confidence_values = sorted({run.confidence for run in runs if run.confidence})
    status_values = sorted({run.status for run in runs})
    behavior_changed = (
        len(bullet_counts) > 1 or len(confidence_values) > 1 or len(status_values) > 1
    )
    return UrlBehaviorComparison(
        url=url,
        run_count=len(runs),
        behavior_changed=behavior_changed,
        latest_status=latest.status,
        latest_confidence=latest.confidence,
        latest_bullet_count=latest.bullet_count,
        bullet_counts=bullet_counts,
        confidence_values=confidence_values,
        status_values=status_values,
        runs=ordered,
    )
