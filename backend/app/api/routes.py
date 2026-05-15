from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import get_live_explanation_service
from app.application.live_explanation_service import LiveExplanationService
from app.config import get_settings
from app.domain.models import ExplanationResponse

router = APIRouter(prefix="/api")
LIVE_SERVICE_DEPENDENCY = Depends(get_live_explanation_service)


class ExplainRequest(BaseModel):
    url: str = Field(min_length=1)
    include_debug: bool = False


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


def _live_search_is_configured(settings: Any) -> bool:
    try:
        settings.require_live_search_provider()
    except Exception:
        return False
    return True
