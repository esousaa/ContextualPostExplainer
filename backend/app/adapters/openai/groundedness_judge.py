import json
from typing import Any

import structlog
from openai import AsyncOpenAI, OpenAIError
from pydantic import SecretStr, ValidationError

from app.adapters.openai.client import build_openai_client
from app.adapters.openai.prompt_loader import load_prompt
from app.adapters.openai.schemas import GroundednessJudgeOutput
from app.domain.errors import ExternalProviderError
from app.domain.models import Evidence, ExplanationBullet, GroundednessAssessment
from app.eval.groundedness import score_for_verdict
from app.observability.redaction import redact_text
from app.ports.groundedness_judge import GroundednessJudge

logger = structlog.get_logger(__name__)

MAX_SOURCE_CHARS = 5000
GROUNDEDNESS_MAX_OUTPUT_TOKENS = 1200
GROUNDEDNESS_MAX_ATTEMPTS = 2


class OpenAIGroundednessJudge(GroundednessJudge):
    def __init__(
        self,
        api_key: SecretStr,
        judge_model: str,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._client = client or build_openai_client(api_key)
        self._judge_model = judge_model

    async def judge(
        self,
        bullet_index: int,
        bullet: ExplanationBullet,
        cited_sources: list[Evidence],
    ) -> GroundednessAssessment:
        payload = {
            "bullet": {
                "text": bullet.text,
                "claim_label": bullet.claim_label,
                "context_modifiers": bullet.context_modifiers,
                "source_ids": bullet.source_ids,
            },
            "cited_sources": [_source_payload(source) for source in cited_sources],
        }
        parsed = await self._request_groundedness(payload)

        return GroundednessAssessment(
            bullet_index=bullet_index,
            verdict=parsed.verdict,
            score=score_for_verdict(parsed.verdict),
            reason=parsed.reason,
            source_ids=bullet.source_ids,
        )

    async def _request_groundedness(self, payload: dict[str, Any]) -> GroundednessJudgeOutput:
        last_error: ValidationError | None = None

        for attempt in range(1, GROUNDEDNESS_MAX_ATTEMPTS + 1):
            try:
                response = await self._client.responses.create(
                    model=self._judge_model,
                    instructions=load_prompt("groundedness_judge"),
                    input=json.dumps(payload, ensure_ascii=False),
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "groundedness_judge",
                            "schema": GroundednessJudgeOutput.model_json_schema(),
                            "strict": True,
                        }
                    },
                    max_output_tokens=GROUNDEDNESS_MAX_OUTPUT_TOKENS,
                )
            except OpenAIError as exc:
                logger.error("groundedness_judge_failed", error=redact_text(str(exc)))
                raise ExternalProviderError("OpenAI groundedness judge failed.") from exc

            output_text = getattr(response, "output_text", None)
            if not isinstance(output_text, str) or not output_text.strip():
                logger.warning(
                    "groundedness_judge_empty_output",
                    attempt=attempt,
                    max_attempts=GROUNDEDNESS_MAX_ATTEMPTS,
                )
                continue

            try:
                return GroundednessJudgeOutput.model_validate_json(output_text)
            except ValidationError as exc:
                last_error = exc
                logger.warning(
                    "groundedness_judge_schema_retry",
                    attempt=attempt,
                    max_attempts=GROUNDEDNESS_MAX_ATTEMPTS,
                    error=redact_text(str(exc)),
                )

        if last_error is not None:
            logger.error("groundedness_judge_schema_failed", error=redact_text(str(last_error)))
            raise ExternalProviderError(
                "OpenAI returned invalid groundedness output."
            ) from last_error

        raise ExternalProviderError("OpenAI returned an empty groundedness assessment.")


def _source_payload(source: Evidence) -> dict[str, Any]:
    return {
        "id": source.id,
        "title": source.title,
        "url": source.url.unicode_string() if source.url else None,
        "source_type": source.source_type,
        "source_category": source.source_category,
        "source_role": source.source_role,
        "content": source.content[:MAX_SOURCE_CHARS],
    }
