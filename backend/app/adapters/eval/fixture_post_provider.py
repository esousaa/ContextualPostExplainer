import json
from pathlib import Path

from app.domain.models import PostData


class FixturePostProvider:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    async def fetch_case_post(self, fixture_path: str) -> PostData:
        path = self._base_dir / fixture_path
        payload = json.loads(path.read_text(encoding="utf-8"))
        return PostData.model_validate(payload)
