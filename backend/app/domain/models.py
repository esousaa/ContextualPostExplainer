from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

SourceCategory = Literal[
    "primary_official",
    "court_document",
    "news_outlet",
    "fact_checking",
    "expert_commentary",
    "social_post",
    "thread_comment",
    "unknown",
]
SourceRole = Literal[
    "original_post",
    "primary_evidence",
    "official_position",
    "independent_context",
    "author_interpretation",
    "public_reaction",
    "background_support",
    "image_observation",
]
ClaimLabel = Literal[
    "confirmed_fact",
    "official_position",
    "author_interpretation",
    "public_reaction",
]
ContextModifier = Literal[
    "background_context",
    "legal_context",
    "political_context",
    "timeline_context",
]
WarningSeverity = Literal["info", "warning"]
GroundednessVerdict = Literal["supported", "partially_supported", "unsupported"]


class ValidationWarning(BaseModel):
    severity: WarningSeverity
    code: str
    message: str
    bullet_index: int | None = None


class ImageContext(BaseModel):
    url: HttpUrl | None = None
    alt_text: str | None = None
    ocr_text: str | None = None
    description: str | None = None
    image_type: str | None = None


class PostAuthor(BaseModel):
    handle: str
    display_name: str | None = None
    did: str | None = None


class PostData(BaseModel):
    url: HttpUrl
    platform: Literal["bluesky"]
    author: PostAuthor
    text: str
    created_at: datetime | None = None
    images: list[ImageContext] = Field(default_factory=list)
    links: list[HttpUrl] = Field(default_factory=list)
    parent_text: str | None = None
    quote_text: str | None = None
    thread_text: str | None = None


class SearchResult(BaseModel):
    provider: str
    query: str
    title: str
    url: HttpUrl
    snippet: str
    rank: int = Field(ge=1)
    canonical_url: HttpUrl | None = None


class Evidence(BaseModel):
    id: str
    title: str
    url: HttpUrl | None = None
    snippet: str
    content: str
    source_type: Literal["web", "social", "thread", "fixture", "image"]
    provider: str | None = None
    query: str | None = None
    canonical_url: HttpUrl | None = None
    published_at: datetime | None = None
    publisher: str | None = None
    source_category: SourceCategory = "unknown"
    source_role: SourceRole = "background_support"


class RankedEvidence(Evidence):
    relevance_score: float = Field(ge=0.0)


class ExplanationBullet(BaseModel):
    text: str
    source_ids: list[str]
    claim_label: ClaimLabel = "confirmed_fact"
    context_modifiers: list[ContextModifier] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    warnings: list[ValidationWarning] = Field(default_factory=list)

    @field_validator("source_ids")
    @classmethod
    def require_source_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("source_ids must not be empty")
        return value

    @field_validator("warnings", mode="before")
    @classmethod
    def normalize_warnings(cls, value):
        return _normalize_warning_values(value)


class Explanation(BaseModel):
    bullets: list[ExplanationBullet] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    warnings: list[ValidationWarning] = Field(default_factory=list)

    @field_validator("warnings", mode="before")
    @classmethod
    def normalize_warnings(cls, value):
        return _normalize_warning_values(value)


class ExplanationResponse(BaseModel):
    post: PostData | None = None
    explanation: list[ExplanationBullet] = Field(default_factory=list)
    sources: list[Evidence] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    warnings: list[ValidationWarning] = Field(default_factory=list)
    execution_time_ms: int = Field(ge=0)

    @field_validator("warnings", mode="before")
    @classmethod
    def normalize_warnings(cls, value):
        return _normalize_warning_values(value)


class EvalCase(BaseModel):
    id: str
    description: str
    post_fixture: str
    evidence_fixture: str
    must_include_facts: list[str] = Field(default_factory=list)
    must_not_claim: list[str] = Field(default_factory=list)
    requires_citations: bool = True
    minimum_sources: int = Field(default=1, ge=0)
    tags: list[str] = Field(default_factory=list)


class EvalMetrics(BaseModel):
    fact_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    citation_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    hallucination_penalty: float | None = Field(default=None, ge=0.0, le=1.0)
    groundedness: float | None = Field(default=None, ge=0.0, le=1.0)
    usefulness: float | None = Field(default=None, ge=1.0, le=5.0)


class GroundednessAssessment(BaseModel):
    bullet_index: int = Field(ge=0)
    verdict: GroundednessVerdict
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    source_ids: list[str] = Field(default_factory=list)


def _normalize_warning_values(value):
    if value is None:
        return []
    normalized = []
    for item in value:
        if isinstance(item, str):
            normalized.append(
                ValidationWarning(
                    severity="warning",
                    code="GENERAL_WARNING",
                    message=item,
                )
            )
        else:
            normalized.append(item)
    return normalized
