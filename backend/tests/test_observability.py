import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.observability.run_recorder import LocalRunRecorder


@pytest.mark.asyncio
async def test_local_run_recorder_writes_redacted_artifact(tmp_path: Path) -> None:
    recorder = LocalRunRecorder(base_dir=tmp_path)

    await recorder.record_event(
        {
            "run_id": "run_test",
            "event": "node_started",
            "metadata": {"api_key": "sk-secretsecretsecret"},
        }
    )
    await recorder.write_run(
        "live",
        "run_test",
        {"response": {"message": "token sk-secretsecretsecret"}},
    )

    payload = json.loads((tmp_path / "live" / "run_test.json").read_text(encoding="utf-8"))

    assert payload["events"][0]["metadata"]["api_key"] == "[REDACTED]"
    assert payload["response"]["message"] == "token [REDACTED]"


def test_http_responses_include_trace_id(client: TestClient) -> None:
    response = client.get("/api/health", headers={"x-trace-id": "trace-test"})

    assert response.headers["x-trace-id"] == "trace-test"
