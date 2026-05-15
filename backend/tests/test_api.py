from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import get_live_explanation_service
from app.domain.errors import SearchProviderRequiredError
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
    async def explain_url(self, url: str, include_debug: bool = False, progress_callback=None):
        from app.domain.models import ExplanationResponse, PostAuthor, PostData

        if progress_callback:
            await progress_callback(
                {
                    "type": "run_started",
                    "run_id": "run_test",
                    "status": "active",
                    "node_name": None,
                    "step": "Fetching post",
                    "message": "Live analysis started.",
                    "timestamp": "2026-05-15T00:00:00+00:00",
                }
            )
            await progress_callback(
                {
                    "type": "node_completed",
                    "run_id": "run_test",
                    "status": "completed",
                    "node_name": "fetch_bluesky_post_thread",
                    "step": "Fetching post",
                    "message": "Fetching post completed.",
                    "timestamp": "2026-05-15T00:00:01+00:00",
                    "duration_ms": 1,
                }
            )

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


class FailingLiveExplanationService:
    async def explain_url(self, url: str, include_debug: bool = False, progress_callback=None):
        raise SearchProviderRequiredError(
            "Live mode requires SEARCH_PROVIDER and the matching provider API key."
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


def test_explain_stream_returns_sse_events(client: TestClient, monkeypatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave-key")
    app.dependency_overrides[get_live_explanation_service] = lambda: FakeLiveExplanationService()

    try:
        with client.stream(
            "POST",
            "/api/explain/stream",
            json={"url": "https://bsky.app/profile/example.bsky.social/post/abc"},
        ) as response:
            body = response.read().decode("utf-8")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: progress" in body
    assert '"type": "run_started"' in body
    assert '"type": "node_completed"' in body
    assert "event: result" in body


def test_explain_stream_returns_domain_errors_as_sse(client: TestClient, monkeypatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave-key")
    app.dependency_overrides[get_live_explanation_service] = lambda: FailingLiveExplanationService()

    try:
        with client.stream(
            "POST",
            "/api/explain/stream",
            json={"url": "https://bsky.app/profile/example.bsky.social/post/abc"},
        ) as response:
            body = response.read().decode("utf-8")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "event: error" in body
    assert '"error": "search_provider_required"' in body
