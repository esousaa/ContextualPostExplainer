import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from starlette.responses import StreamingResponse

from app.adapters.bluesky.url_parser import parse_bluesky_post_url
from app.analysis.run_analysis import AnalysisOverview, LocalAnalysisStore
from app.api.dependencies import get_live_explanation_service
from app.application.live_explanation_service import LiveExplanationService
from app.config import get_settings
from app.domain.errors import DomainError, UnsupportedPlatformError
from app.domain.models import ExplanationResponse
from app.observability.run_store import LocalRunStore, RunDetail, RunSummary

STREAM_DONE = object()
HEARTBEAT_INTERVAL_SECONDS = 5.0
API_SERVICE_NAME = "contextual-post-explainer-api"
API_VERSION = "0.1.0"

router = APIRouter(prefix="/api")
LIVE_SERVICE_DEPENDENCY = Depends(get_live_explanation_service)


class ExplainRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    include_debug: bool = False

    @field_validator("url")
    @classmethod
    def must_be_bluesky_url(cls, v: str) -> str:
        try:
            parse_bluesky_post_url(v)
        except UnsupportedPlatformError as exc:
            raise ValueError("URL must be a Bluesky post URL (bsky.app).") from exc
        return v


class RunListResponse(BaseModel):
    runs: list[RunSummary]


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": API_SERVICE_NAME,
        "version": API_VERSION,
    }


@router.get("/config/status")
async def config_status() -> dict[str, Any]:
    try:
        settings = get_settings()
    except Exception as exc:
        return {
            "status": "invalid",
            "error": str(exc),
        }

    live_configured = _live_search_is_configured(settings)
    eval_fixture_dir_exists = _eval_fixture_dir_exists(settings.eval_fixture_dir)

    return {
        "status": "ready" if live_configured else "degraded",
        "openai": {
            "generation_model": settings.openai_generation_model,
            "judge_model": settings.openai_judge_model,
            "embedding_model": settings.openai_embedding_model,
            "vision_model": settings.openai_vision_model,
        },
        "live_search": {
            "provider": settings.search_provider,
            "configured": live_configured,
        },
        "eval": {
            "fixture_dir": str(settings.eval_fixture_dir),
            "configured": eval_fixture_dir_exists,
        },
        "diagnostics": {
            "live_mode_ready": live_configured,
            "eval_mode_ready": eval_fixture_dir_exists,
        },
    }


EXPLAIN_TIMEOUT_SECONDS = 120.0


@router.post("/explain", response_model=ExplanationResponse)
async def explain(
    request: ExplainRequest,
    service: LiveExplanationService = LIVE_SERVICE_DEPENDENCY,
) -> ExplanationResponse:
    try:
        return await asyncio.wait_for(
            service.explain_url(url=request.url, include_debug=request.include_debug),
            timeout=EXPLAIN_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Request timed out.") from exc


@router.post("/explain/stream")
async def explain_stream(
    request: ExplainRequest,
    service: LiveExplanationService = LIVE_SERVICE_DEPENDENCY,
) -> StreamingResponse:
    queue: asyncio.Queue[tuple[str, Any] | object] = asyncio.Queue()

    async def progress_callback(event: dict[str, Any]) -> None:
        await queue.put(("progress", event))

    async def run_flow() -> None:
        try:
            response = await service.explain_url(
                url=request.url,
                include_debug=request.include_debug,
                progress_callback=progress_callback,
            )
            await queue.put(("result", response.model_dump(mode="json")))
        except DomainError as exc:
            await queue.put(
                (
                    "error",
                    {
                        "error": exc.error_code,
                        "message": exc.message,
                        "status": int(exc.status_code),
                    },
                )
            )
        except Exception:
            await queue.put(
                (
                    "error",
                    {
                        "error": "unexpected_error",
                        "message": "Unexpected backend error while streaming the live analysis.",
                        "status": 500,
                    },
                )
            )
        finally:
            await queue.put(STREAM_DONE)

    async def event_stream():
        task = asyncio.create_task(run_flow())
        last_progress: dict[str, Any] | None = None

        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), HEARTBEAT_INTERVAL_SECONDS)
                except TimeoutError:
                    yield _format_sse("progress", _heartbeat_event(last_progress))
                    continue

                if item is STREAM_DONE:
                    break

                event_name, payload = item
                if event_name == "progress":
                    last_progress = payload
                yield _format_sse(event_name, payload)
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs", response_model=RunListResponse)
async def list_runs(
    mode: Literal["live", "eval"] = "live",
    limit: int = Query(default=50, ge=1, le=200),
) -> RunListResponse:
    return RunListResponse(runs=LocalRunStore().list_runs(mode=mode, limit=limit))


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: str,
    mode: Literal["live", "eval"] = "live",
) -> RunDetail:
    detail = LocalRunStore().get_run(run_id=run_id, mode=mode)
    if detail is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return detail


@router.get("/analysis", response_model=AnalysisOverview)
async def get_analysis_overview(
    limit: int = Query(default=200, ge=1, le=500),
) -> AnalysisOverview:
    return LocalAnalysisStore().overview(limit=limit)


def _live_search_is_configured(settings: Any) -> bool:
    try:
        settings.require_live_search_provider()
    except Exception:
        return False
    return True


def _eval_fixture_dir_exists(path: Path) -> bool:
    if path.exists():
        return True
    if path.is_absolute():
        return False
    repo_root = Path(__file__).resolve().parents[3]
    return (repo_root / path).exists()


def _format_sse(event_name: str, payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_name}\ndata: {data}\n\n"


def _heartbeat_event(last_progress: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "type": "heartbeat",
        "run_id": last_progress.get("run_id") if last_progress else None,
        "status": "active",
        "node_name": last_progress.get("node_name") if last_progress else None,
        "step": last_progress.get("step") if last_progress else "Fetching post",
        "message": "Live analysis is still running.",
        "timestamp": datetime.now(UTC).isoformat(),
    }
