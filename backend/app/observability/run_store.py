import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.graphs.live_graph import LIVE_NODE_STEPS

RunMode = Literal["live", "eval"]
RunStatus = Literal["completed", "no_explanation", "failed", "unknown"]


class RunSummary(BaseModel):
    run_id: str
    mode: RunMode
    generated_at: str | None = None
    input_url: str | None = None
    status: RunStatus
    confidence: str | None = None
    execution_time_ms: int | None = None
    source_count: int = Field(ge=0)
    cited_source_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    bullet_count: int = Field(ge=0)
    post_author: str | None = None
    post_text: str | None = None


class RunTimelineItem(BaseModel):
    node_name: str
    step: str
    status: RunStatus
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None


class RunDetail(BaseModel):
    summary: RunSummary
    post: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    timeline: list[RunTimelineItem]
    queries: list[str]
    metrics: dict[str, Any]
    sources: list[dict[str, Any]]
    cited_sources: list[dict[str, Any]]
    warnings: list[Any]
    error: dict[str, Any] | None = None
    raw: dict[str, Any]


class LocalRunStore:
    def __init__(self, base_dir: Path = Path("runs")) -> None:
        self._base_dir = base_dir

    def list_runs(self, mode: RunMode = "live", limit: int = 50) -> list[RunSummary]:
        documents = [_load_json(path) for path in self._run_paths(mode)]
        summaries = [_summary(document) for document in documents if document]
        summaries.sort(key=lambda item: _datetime_sort_key(item.generated_at), reverse=True)
        return summaries[:limit]

    def get_run(self, run_id: str, mode: RunMode = "live") -> RunDetail | None:
        if not _safe_run_id(run_id):
            return None

        document = _load_json(self._base_dir / mode / f"{run_id}.json")
        if not document:
            return None

        summary = _summary(document)
        return RunDetail(
            summary=summary,
            post=_post_payload(document),
            response=document.get("response"),
            timeline=_timeline(document),
            queries=[str(query) for query in document.get("queries", [])],
            metrics=document.get("metrics", {}),
            sources=document.get("sources", []),
            cited_sources=document.get("cited_sources", []),
            warnings=document.get("warnings", []),
            error=document.get("error"),
            raw=document,
        )

    def _run_paths(self, mode: RunMode) -> list[Path]:
        directory = self._base_dir / mode
        if not directory.exists():
            return []
        return list(directory.glob("*.json"))


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _summary(document: dict[str, Any]) -> RunSummary:
    response = document.get("response") or {}
    post = _post_payload(document) or {}
    author = post.get("author") or {}
    explanation = response.get("explanation") or []
    response_sources = response.get("sources") or []
    sources = document.get("sources") or response_sources
    cited_sources = document.get("cited_sources") or response_sources
    warnings = document.get("warnings") or response.get("warnings") or []

    return RunSummary(
        run_id=str(document["run_id"]),
        mode=document.get("mode", "live"),
        generated_at=document.get("generated_at"),
        input_url=document.get("input_url") or post.get("url"),
        status=_status(document),
        confidence=response.get("confidence"),
        execution_time_ms=response.get("execution_time_ms"),
        source_count=len(sources),
        cited_source_count=len(cited_sources),
        warning_count=len(warnings),
        bullet_count=len(explanation),
        post_author=author.get("handle"),
        post_text=post.get("text"),
    )


def _post_payload(document: dict[str, Any]) -> dict[str, Any] | None:
    response = document.get("response") or {}
    post = response.get("post")
    return post if isinstance(post, dict) else None


def _status(document: dict[str, Any]) -> RunStatus:
    if document.get("status") == "failed" or document.get("error"):
        return "failed"
    response = document.get("response") or {}
    if response and not response.get("explanation"):
        return "no_explanation"
    if response:
        return "completed"
    return "unknown"


def _timeline(document: dict[str, Any]) -> list[RunTimelineItem]:
    items: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for event in document.get("events", []):
        node_name = event.get("node_name")
        if not node_name:
            continue
        if node_name not in items:
            items[node_name] = {
                "node_name": node_name,
                "step": LIVE_NODE_STEPS.get(node_name, _readable_node_name(node_name)),
                "status": "unknown",
                "started_at": None,
                "completed_at": None,
                "duration_ms": None,
            }
            order.append(node_name)

        if event.get("event") == "node_started":
            items[node_name]["started_at"] = event.get("timestamp")
            items[node_name]["status"] = "unknown"
        elif event.get("event") == "node_completed":
            items[node_name]["completed_at"] = event.get("timestamp")
            items[node_name]["duration_ms"] = event.get("duration_ms")
            items[node_name]["status"] = "completed"

    if _status(document) == "failed":
        _mark_open_node_failed(items, order)
    elif document.get("response"):
        _mark_legacy_finalize_completed(items, document)

    return [RunTimelineItem.model_validate(items[node_name]) for node_name in order]


def _mark_open_node_failed(items: dict[str, dict[str, Any]], order: list[str]) -> None:
    for node_name in reversed(order):
        item = items[node_name]
        if item["completed_at"] is None:
            item["status"] = "failed"
            return


def _mark_legacy_finalize_completed(
    items: dict[str, dict[str, Any]],
    document: dict[str, Any],
) -> None:
    item = items.get("finalize_response")
    if not item or item["completed_at"] is not None:
        return

    item["completed_at"] = document.get("generated_at")
    item["status"] = "completed"


def _readable_node_name(node_name: str) -> str:
    return node_name.replace("_", " ").title()


def _datetime_sort_key(value: str | None) -> str:
    return value or ""


def _safe_run_id(run_id: str) -> bool:
    return bool(run_id) and "/" not in run_id and "\\" not in run_id and run_id not in {".", ".."}
