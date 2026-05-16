import json
import re
from typing import Any

import structlog
from openai import AsyncOpenAI, OpenAIError
from pydantic import SecretStr, ValidationError

from app.adapters.openai.client import build_openai_client
from app.adapters.openai.prompt_loader import load_prompt
from app.adapters.openai.schemas import LLMExplanationOutput, QueryDecompositionOutput
from app.domain.errors import ExternalProviderError
from app.domain.models import Evidence, Explanation, ExplanationBullet, PostData
from app.observability.redaction import redact_text
from app.ports.llm_client import LLMClient

logger = structlog.get_logger(__name__)

REPAIR_INSTRUCTION = """
Preserve useful explanatory bullets whenever possible. First try to repair by:
- changing claim_label to author_interpretation when the bullet explains the original
  author's framing, criticism, opinion, rhetoric, hope, or prediction, and cite the
  original post source;
- changing claim_label to public_reaction when the bullet explains replies, comments,
  reposts, or broader social reaction, and cite thread/social sources;
- changing claim_label to official_position when the bullet attributes a position,
  allegation, demand, or argument to a named organization, agency, court, campaign,
  official, or party involved, and cite a compatible official, court, primary, or
  recognized news source;
- rewriting sensitive claims as attributed allegations or procedural context when the
  cited sources support only the existence of the allegation, lawsuit, investigation,
  charge, or dispute, not the truth of the underlying accusation.

Omit a bullet only when no compatible source can support a corrected contextual version.
Return 3 to 5 bullets if at least 3 useful corrected bullets can be supported; otherwise
return zero bullets.
""".strip()


class OpenAILLMClient(LLMClient):
    def __init__(
        self,
        api_key: SecretStr,
        generation_model: str,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._client = client or build_openai_client(api_key)
        self._generation_model = generation_model

    async def decompose_queries(self, post: PostData) -> list[str]:
        payload = {
            "post": _post_payload(post),
        }
        output = await self._create_structured_response(
            prompt_name="query_decomposition",
            schema_name="query_decomposition",
            schema=QueryDecompositionOutput.model_json_schema(),
            payload=payload,
            max_output_tokens=700,
        )

        try:
            parsed = QueryDecompositionOutput.model_validate_json(output)
        except ValidationError as exc:
            logger.error("query_decomposition_schema_failed", error=redact_text(str(exc)))
            raise ExternalProviderError(
                "OpenAI returned invalid query decomposition output."
            ) from exc

        return parsed.queries

    async def generate_explanation(
        self,
        post: PostData,
        evidence: list[Evidence],
    ) -> Explanation:
        if not evidence:
            return _insufficient_evidence_explanation()

        output = await self._create_structured_response(
            prompt_name="explanation_generation",
            schema_name="explanation_generation",
            schema=LLMExplanationOutput.model_json_schema(),
            payload={
                "post": _post_payload(post),
                "sources": [_evidence_payload(source) for source in evidence],
            },
            max_output_tokens=1800,
        )
        return _parse_explanation_output(output)

    async def repair_explanation(
        self,
        post: PostData,
        evidence: list[Evidence],
        invalid_payload: str,
        validation_error: str,
    ) -> Explanation:
        output = await self._create_structured_response(
            prompt_name="explanation_generation",
            schema_name="explanation_repair",
            schema=LLMExplanationOutput.model_json_schema(),
            payload={
                "post": _post_payload(post),
                "sources": [_evidence_payload(source) for source in evidence],
                "invalid_payload": invalid_payload,
                "validation_error": validation_error,
                "repair_instruction": REPAIR_INSTRUCTION,
            },
            max_output_tokens=1800,
        )
        return _parse_explanation_output(output)

    async def _create_structured_response(
        self,
        prompt_name: str,
        schema_name: str,
        schema: dict[str, Any],
        payload: dict[str, Any],
        max_output_tokens: int,
    ) -> str:
        try:
            response = await self._client.responses.create(
                model=self._generation_model,
                instructions=load_prompt(prompt_name),
                input=json.dumps(payload, ensure_ascii=False),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
                max_output_tokens=max_output_tokens,
            )
        except OpenAIError as exc:
            logger.error("openai_response_failed", error=redact_text(str(exc)))
            raise ExternalProviderError("OpenAI response generation failed.") from exc

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise ExternalProviderError("OpenAI returned an empty response.")
        return output_text


def _parse_explanation_output(output: str) -> Explanation:
    try:
        parsed = LLMExplanationOutput.model_validate_json(output)
    except ValidationError as exc:
        logger.error("explanation_schema_failed", error=redact_text(str(exc)))
        raise ExternalProviderError("OpenAI returned invalid explanation output.") from exc

    return Explanation(
        bullets=[
            ExplanationBullet(
                text=_clean_bullet_text(bullet.text),
                claim_label=bullet.claim_label,
                context_modifiers=bullet.context_modifiers,
                source_ids=bullet.source_ids,
                confidence=bullet.confidence,
                warnings=bullet.warnings,
            )
            for bullet in parsed.bullets
        ],
        confidence=parsed.confidence,
        warnings=parsed.warnings,
    )


def _post_payload(post: PostData) -> dict[str, Any]:
    return {
        "url": post.url.unicode_string(),
        "platform": post.platform,
        "author": post.author.model_dump(mode="json"),
        "text": post.text,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "links": [link.unicode_string() for link in post.links],
        "parent_text": post.parent_text,
        "quote_text": post.quote_text,
        "thread_text": post.thread_text,
        "images": [image.model_dump(mode="json") for image in post.images],
    }


def _evidence_payload(source: Evidence) -> dict[str, Any]:
    return {
        "id": source.id,
        "title": source.title,
        "url": source.url.unicode_string() if source.url else None,
        "snippet": source.snippet,
        "content": source.content,
        "source_type": source.source_type,
        "source_category": source.source_category,
        "source_role": source.source_role,
        "publisher": source.publisher,
        "provider": source.provider,
        "query": source.query,
    }


def _insufficient_evidence_explanation() -> Explanation:
    return Explanation(
        bullets=[],
        confidence="low",
        warnings=[
            "Insufficient evidence to generate a reliable explanation.",
            "No explanatory bullets were generated to avoid unsupported claims.",
        ],
    )


def _clean_bullet_text(text: str) -> str:
    return re.sub(r"\s*\[[\w,:;\s-]+\]\s*$", "", text).strip()
