from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models import ClaimLabel, ContextModifier, GroundednessVerdict


class QueryDecompositionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: list[str] = Field(min_length=2, max_length=4)

    @field_validator("queries")
    @classmethod
    def normalize_queries(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(query.strip() for query in value if query.strip()))
        if not 2 <= len(normalized) <= 4:
            raise ValueError("queries must contain 2 to 4 non-empty unique values")
        return normalized


class LLMExplanationBullet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    claim_label: ClaimLabel
    context_modifiers: list[ContextModifier]
    source_ids: list[str] = Field(min_length=1)
    confidence: Literal["high", "medium", "low"]
    warnings: list[str]


class LLMExplanationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bullets: list[LLMExplanationBullet]
    confidence: Literal["high", "medium", "low"]
    warnings: list[str]


class GroundednessJudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: GroundednessVerdict
    reason: str = Field(min_length=1)


class ImageAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocr_text: str
    description: str
    image_type: str
    warnings: list[str]
