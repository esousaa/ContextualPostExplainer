import asyncio
import json
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.analysis.run_analysis import AnalysisOverview, LocalAnalysisStore
from app.api.dependencies import get_live_explanation_service
from app.application.live_explanation_service import LiveExplanationService
from app.config import Settings, get_settings
from app.domain.errors import DomainError
from app.domain.models import ExplanationResponse
from app.observability.run_store import LocalRunStore, RunDetail, RunSummary

STREAM_DONE = object()
HEARTBEAT_INTERVAL_SECONDS = 5.0

router = APIRouter(prefix="/api")
LIVE_SERVICE_DEPENDENCY = Depends(get_live_explanation_service)


class ExplainRequest(BaseModel):
    url: str = Field(min_length=1)
    include_debug: bool = False


class RunListResponse(BaseModel):
    runs: list[RunSummary]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/config/status")
async def config_status() -> dict[str, Any]:
    try:
        settings = get_settings()
    except Exception as exc:
        return {
            "status": "invalid",
            "error": str(exc),
        }

    return {
        "status": "ok",
        "openai": {
            "generation_model": settings.openai_generation_model,
            "judge_model": settings.openai_judge_model,
            "embedding_model": settings.openai_embedding_model,
            "vision_model": settings.openai_vision_model,
        },
        "live_search": {
            "provider": settings.search_provider,
            "configured": _live_search_is_configured(settings),
        },
        "eval": {
            "fixture_dir": str(settings.eval_fixture_dir),
        },
    }


@router.post("/explain", response_model=ExplanationResponse)
async def explain(
    request: ExplainRequest,
    service: LiveExplanationService = LIVE_SERVICE_DEPENDENCY,
) -> ExplanationResponse:
    return await service.explain_url(
        url=request.url,
        include_debug=request.include_debug,
    )


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
    return LocalAnalysisStore(default_config=_analysis_default_config()).overview(limit=limit)


def _live_search_is_configured(settings: Any) -> bool:
    try:
        settings.require_live_search_provider()
    except Exception:
        return False
    return True


def _analysis_default_config() -> dict[str, str | None]:
    try:
        settings = get_settings()
    except Exception:
        return {}
    return _settings_config(settings)


def _settings_config(settings: Settings) -> dict[str, str | None]:
    return {
        "openai_generation_model": settings.openai_generation_model,
        "openai_judge_model": settings.openai_judge_model,
        "openai_embedding_model": settings.openai_embedding_model,
        "openai_vision_model": settings.openai_vision_model,
    }


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
