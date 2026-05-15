import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.observability.redaction import redact_text
from app.ports.run_recorder import RunRecorder


class LocalRunRecorder(RunRecorder):
    def __init__(self, base_dir: Path = Path("runs")) -> None:
        self._base_dir = base_dir
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def record_event(self, event: dict[str, Any]) -> None:
        run_id = str(event["run_id"])
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            **_redact(event),
        }
        self._events[run_id].append(payload)

    async def write_run(self, mode: str, run_id: str, payload: dict[str, Any]) -> None:
        directory = self._base_dir / mode
        directory.mkdir(parents=True, exist_ok=True)
        document = {
            "run_id": run_id,
            "mode": mode,
            "generated_at": datetime.now(UTC).isoformat(),
            "events": self._events.get(run_id, []),
            **_redact(payload),
        }
        (directory / f"{run_id}.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value
