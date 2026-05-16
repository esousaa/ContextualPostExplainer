import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from app.observability.redaction import redact_text
from app.ports.run_recorder import RunRecorder

SENSITIVE_KEY_PARTS = ("api_key", "token", "secret", "password", "authorization")


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


def _redact(value: Any, key: str | None = None) -> Any:
    if key and _is_sensitive_key(key):
        return _redacted_secret_value(value)
    if isinstance(value, SecretStr):
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {item_key: _redact(item, str(item_key)) for item_key, item in value.items()}
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.casefold()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def _redacted_secret_value(value: Any) -> Any:
    if value in (None, ""):
        return value
    return "[REDACTED]"
