import json
from pathlib import Path

from app.application.source_classification import classify_evidence
from app.domain.models import Evidence


class FixtureEvidenceProvider:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    async def fetch_case_evidence(self, fixture_path: str) -> list[Evidence]:
        path = self._base_dir / fixture_path
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [classify_evidence(Evidence.model_validate(item)) for item in payload]
