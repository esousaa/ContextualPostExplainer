import json
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
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "contextual-post-explainer-api"
    assert payload["version"]


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


def test_config_status_reports_live_readiness(client: TestClient, monkeypatch) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave-key")

    response = client.get("/api/config/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["live_search"]["configured"] is True
    assert payload["diagnostics"]["live_mode_ready"] is True


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


def test_explain_rejects_urls_that_do_not_match_bluesky_post_contract(
    client: TestClient,
    monkeypatch,
) -> None:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SEARCH_PROVIDER", "brave")
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave-key")

    for url in (
        "https://evil.com/?next=bsky.app/profile/example.bsky.social/post/abc",
        "https://bsky.app.evil.com/profile/example.bsky.social/post/abc",
        "https://bsky.app/profile/example.bsky.social/feed/abc",
    ):
        response = client.post("/api/explain", json={"url": url})

        assert response.status_code == 422
        assert "Bluesky post URL" in response.text


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


def test_runs_api_lists_local_run_artifacts(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_run_fixture(tmp_path, "run_abcdef")

    response = client.get("/api/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["run_id"] == "run_abcdef"
    assert payload["runs"][0]["status"] == "completed"
    assert payload["runs"][0]["bullet_count"] == 1
    assert payload["runs"][0]["cited_source_count"] == 1


def test_runs_api_returns_detail_with_timeline(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_run_fixture(tmp_path, "run_abcdef")

    response = client.get("/api/runs/run_abcdef")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["run_id"] == "run_abcdef"
    assert payload["timeline"][0]["node_name"] == "fetch_source_pages"
    assert payload["timeline"][0]["step"] == "Reading sources"
    assert payload["timeline"][0]["status"] == "completed"
    assert payload["raw"]["run_id"] == "run_abcdef"


def test_runs_api_marks_zero_bullet_runs_as_no_explanation(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_run_fixture(tmp_path, "run_empty", explanation=[])

    response = client.get("/api/runs/run_empty")

    assert response.status_code == 200
    assert response.json()["summary"]["status"] == "no_explanation"


def test_runs_api_marks_legacy_open_finalize_as_completed(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_run_fixture(
        tmp_path,
        "run_legacy",
        events=[
            {
                "timestamp": "2026-05-15T12:00:00+00:00",
                "event": "node_started",
                "run_id": "run_legacy",
                "mode": "live",
                "node_name": "finalize_response",
            }
        ],
    )

    response = client.get("/api/runs/run_legacy")

    assert response.status_code == 200
    finalize = response.json()["timeline"][0]
    assert finalize["status"] == "completed"
    assert finalize["completed_at"] == "2026-05-15T12:00:00+00:00"


def test_analysis_api_aggregates_provider_and_url_behavior(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_run_fixture(
        tmp_path,
        "run_tavily",
        config={"search_provider": "tavily", "openai_embedding_model": "small"},
        metrics={"search_results_received": 10, "search_results_by_provider": {"tavily": 10}},
    )
    _write_run_fixture(
        tmp_path,
        "run_composite",
        explanation=[],
        config={"search_provider": "composite", "openai_embedding_model": "small"},
        metrics={
            "search_results_received": 20,
            "search_results_by_provider": {"brave": 10, "tavily": 10},
            "search_provider_overlap_count": 2,
        },
    )

    response = client.get("/api/analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 2
    assert payload["total_urls"] == 1
    assert {item["key"] for item in payload["provider_aggregates"]} == {
        "tavily",
        "composite",
    }
    comparison = payload["url_comparisons"][0]
    assert comparison["behavior_changed"] is True
    assert comparison["bullet_counts"] == [0, 1]


def test_analysis_api_keeps_legacy_runs_without_model_metadata_unknown(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    _write_run_fixture(
        tmp_path,
        "run_legacy_models",
        config=None,
        metrics={"search_results_received": 10, "search_results_by_provider": {"tavily": 10}},
    )

    response = client.get("/api/analysis")

    assert response.status_code == 200
    assert response.json()["llm_aggregates"][0]["key"] == (
        "gen=unknown | judge=unknown | embed=unknown | vision=unknown"
    )


def test_analysis_api_uses_latest_retry_for_comparison_metrics(
    client: TestClient,
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    config = {
        "search_provider": "tavily",
        "comparison_group_id": "llm_eval",
        "comparison_config_id": "newer_full",
    }
    _write_run_fixture(
        tmp_path,
        "run_failed_first",
        explanation=[],
        config=config,
        generated_at="2026-05-15T12:00:00+00:00",
    )
    _write_run_fixture(
        tmp_path,
        "run_retry_success",
        config=config,
        generated_at="2026-05-15T12:05:00+00:00",
    )

    response = client.get("/api/analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_runs"] == 1
    provider = payload["provider_aggregates"][0]
    assert provider["run_count"] == 1
    assert provider["completed_count"] == 1
    assert provider["no_explanation_count"] == 0


def _write_run_fixture(
    tmp_path: Path,
    run_id: str,
    explanation: list[dict] | None = None,
    events: list[dict] | None = None,
    config: dict | None = None,
    metrics: dict | None = None,
    generated_at: str = "2026-05-15T12:00:00+00:00",
) -> None:
    directory = tmp_path / "runs" / "live"
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "mode": "live",
        "generated_at": generated_at,
        "events": events
        if events is not None
        else [
            {
                "timestamp": "2026-05-15T12:00:00+00:00",
                "event": "node_started",
                "run_id": run_id,
                "mode": "live",
                "node_name": "fetch_source_pages",
            },
            {
                "timestamp": "2026-05-15T12:00:01+00:00",
                "event": "node_completed",
                "run_id": run_id,
                "mode": "live",
                "node_name": "fetch_source_pages",
                "duration_ms": 1000,
            },
        ],
        "input_url": "https://bsky.app/profile/example.bsky.social/post/abc",
        "queries": ["example query"],
        "metrics": metrics or {"search_results_received": 2},
        **(config or {}),
        "config": config or {},
        "sources": [{"id": "s1"}],
        "cited_sources": [{"id": "s1"}],
        "warnings": [],
        "response": {
            "post": {
                "url": "https://bsky.app/profile/example.bsky.social/post/abc",
                "platform": "bluesky",
                "author": {"handle": "example.bsky.social"},
                "text": "Example post",
                "created_at": None,
                "images": [],
                "links": [],
                "parent_text": None,
                "quote_text": None,
                "thread_text": None,
            },
            "explanation": (
                [{"text": "One.", "source_ids": ["s1"]}] if explanation is None else explanation
            ),
            "sources": [{"id": "s1"}],
            "confidence": "high",
            "warnings": [],
            "execution_time_ms": 1000,
        },
    }
    (directory / f"{run_id}.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
