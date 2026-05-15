from fastapi import Depends

from app.application.live_explanation_service import LiveExplanationService
from app.config import Settings, get_settings

SETTINGS_DEPENDENCY = Depends(get_settings)


def get_live_explanation_service(
    settings: Settings = SETTINGS_DEPENDENCY,
) -> LiveExplanationService:
    return LiveExplanationService(settings)
