from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import get_live_explanation_service
from app.main import app

REQUIRED_ENV = {
    "OPENAI_API_KEY": "test-openai-key",
    "OPENAI_GENERATION_MODEL": "gpt-4o",
    "OPENAI_JUDGE_MODEL": "gpt-4o-mini",
    "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
    "BACKEND_CORS_ORIGINS": '["http://localhost:5173"]',
    "EVAL_FIXTURE_DIR": "eval/fixtures",
}


class FakeLiveExplanationService:
    async def explain_url(self, url: str, include_debug: bool = False):
        from app.domain.models import ExplanationResponse, PostAuthor, PostData

        return ExplanationResponse(
            post=PostData(
                url=url,
                platform="bluesky",
                author=PostAuthor(handle="example.bsky.social"),
                text="Example post",
            ),
            explanation=[],
            sources=[],
            confidence="low",
            warnings=[],
            execution_time_ms=1,
        )


def test_health_does_not_require_runtime_configuration(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_status_reports_invalid_configuration(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in REQUIRED_ENV:
        monkeypatch.delenv(key, raising=False)

    response = client.get("/api/config/status")

    assert response.status_code == 200
    assert response.json()["status"] == "invalid"


def test_explain_requires_live_search_provider(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    response = client.post(
        "/api/explain",
        json={"url": "https://bsky.app/profile/example.bsky.social/post/abc"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "search_provider_required"


def test_explain_uses_live_service_when_live_config_is_valid(
    client: TestClient,
    monkeypatch,
) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave-key")
    app.dependency_overrides[get_live_explanation_service] = lambda: FakeLiveExplanationService()

    try:
        response = client.post(
            "/api/explain",
            json={"url": "https://bsky.app/profile/example.bsky.social/post/abc"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["confidence"] == "low"
