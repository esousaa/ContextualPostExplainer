from functools import lru_cache
from pathlib import Path
from typing import Literal

import structlog
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.errors import ConfigurationError, SearchProviderRequiredError

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr
    openai_generation_model: str
    openai_judge_model: str
    openai_embedding_model: str
    backend_cors_origins: list[str]
    eval_fixture_dir: Path

    openai_vision_model: str | None = None
    search_provider: Literal["brave", "tavily", "composite"] | None = None
    brave_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    bsky_handle: str | None = None
    bsky_app_password: SecretStr | None = None
    comparison_group_id: str | None = None
    comparison_config_id: str | None = None
    log_level: str = Field(default="INFO")

    @field_validator(
        "openai_generation_model",
        "openai_judge_model",
        "openai_embedding_model",
        mode="after",
    )
    @classmethod
    def require_non_empty_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value

    def require_live_search_provider(self) -> None:
        if self.search_provider == "brave" and _secret_is_set(self.brave_api_key):
            return
        if self.search_provider == "tavily" and _secret_is_set(self.tavily_api_key):
            return
        if self.search_provider == "composite" and (
            _secret_is_set(self.brave_api_key) or _secret_is_set(self.tavily_api_key)
        ):
            return

        logger.error(
            "live_search_provider_missing",
            search_provider=self.search_provider,
            has_brave_key=_secret_is_set(self.brave_api_key),
            has_tavily_key=_secret_is_set(self.tavily_api_key),
        )
        raise SearchProviderRequiredError(
            "Live mode requires SEARCH_PROVIDER and the matching provider API key. "
            "Use make eval for fixture-based evaluation."
        )


@lru_cache
def get_settings() -> Settings:
    """Load settings once and convert validation failures to a domain error."""
    try:
        return Settings()
    except Exception as exc:
        logger.error("settings_load_failed", error=str(exc))
        raise ConfigurationError("Required runtime configuration is missing or invalid.") from exc


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def _secret_is_set(value: SecretStr | None) -> bool:
    return bool(value and value.get_secret_value().strip())
