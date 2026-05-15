from typing import Any, Protocol


class RunRecorder(Protocol):
    async def record_event(self, event: dict[str, Any]) -> None: ...

    async def write_run(self, mode: str, run_id: str, payload: dict[str, Any]) -> None: ...
