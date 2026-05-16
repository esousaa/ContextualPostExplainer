from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.errors import CitationValidationError
from app.domain.models import (
    EvalCase,
    Evidence,
    ExplanationBullet,
    ExplanationResponse,
    PostAuthor,
    PostData,
)
from app.domain.validation import CitationValidator


def make_source(source_id: str = "s1") -> Evidence:
    return Evidence(
        id=source_id,
        title="Reference article",
        url="https://example.com/reference",
        snippet="Relevant snippet.",
        content="Relevant source content.",
        source_type="web",
    )


def make_social_source(source_id: str = "thread_original") -> Evidence:
    return Evidence(
        id=source_id,
        title="Original post",
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        snippet="Post snippet.",
        content="Post content.",
        source_type="thread",
        source_category="social_post",
        source_role="original_post",
    )


def make_news_source(source_id: str = "news_1") -> Evidence:
    return Evidence(
        id=source_id,
        title="News report",
        url="https://www.cnn.com/example",
        snippet="News snippet.",
        content="News content.",
        source_type="web",
        source_category="news_outlet",
        source_role="independent_context",
    )


def make_public_statement_source(source_id: str = "statement_1") -> Evidence:
    return Evidence(
        id=source_id,
        title="Public statement",
        url="https://example.org/press/example",
        snippet="The organization released a statement.",
        content="Statement content.",
        source_type="web",
        source_category="unknown",
        source_role="official_position",
    )


def make_bullet(source_id: str = "s1") -> ExplanationBullet:
    return ExplanationBullet(text="Relevant context.", source_ids=[source_id])


def test_explanation_bullet_requires_source_ids() -> None:
    with pytest.raises(ValidationError):
        ExplanationBullet(text="Missing citations.", source_ids=[])


def test_citation_validator_accepts_three_to_five_cited_bullets() -> None:
    validator = CitationValidator()
    bullets = [make_bullet() for _ in range(3)]

    validator.validate(bullets=bullets, sources=[make_source()])


def test_citation_validator_accepts_empty_explanation() -> None:
    validator = CitationValidator()

    validator.validate(bullets=[], sources=[])


def test_citation_validator_rejects_one_or_two_bullets() -> None:
    validator = CitationValidator()

    with pytest.raises(CitationValidationError):
        validator.validate(bullets=[make_bullet()], sources=[make_source()])


def test_citation_validator_rejects_unknown_source_id() -> None:
    validator = CitationValidator()
    bullets = [make_bullet("missing") for _ in range(3)]

    with pytest.raises(CitationValidationError):
        validator.validate(bullets=bullets, sources=[make_source()])


def test_citation_validator_rejects_uncitable_web_source() -> None:
    validator = CitationValidator()
    source = Evidence(
        id="s1",
        title="Reference without URL",
        url=None,
        snippet="Relevant snippet.",
        content="Relevant source content.",
        source_type="web",
    )

    with pytest.raises(CitationValidationError):
        validator.validate(bullets=[make_bullet() for _ in range(3)], sources=[source])


def test_thread_source_can_be_cited_without_url() -> None:
    validator = CitationValidator()
    source = Evidence(
        id="thread_1",
        title="Original thread",
        url=None,
        snippet="Thread snippet.",
        content="Thread content.",
        source_type="thread",
    )

    validator.validate(bullets=[make_bullet("thread_1") for _ in range(3)], sources=[source])


@pytest.mark.parametrize("source_type", ["fixture", "image"])
def test_local_context_sources_can_be_cited_without_url(source_type: str) -> None:
    validator = CitationValidator()
    source = Evidence(
        id="local_1",
        title="Local context",
        url=None,
        snippet="Local snippet.",
        content="Local content.",
        source_type=source_type,
    )

    validator.validate(bullets=[make_bullet("local_1") for _ in range(3)], sources=[source])


def test_citation_validator_warns_when_confirmed_fact_uses_only_social_source() -> None:
    validator = CitationValidator()
    bullets = [
        ExplanationBullet(
            text="The post claim is externally confirmed.",
            source_ids=["thread_original"],
            claim_label="confirmed_fact",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(bullets=bullets, sources=[make_social_source()])

    assert warnings[0].code == "SOCIAL_ONLY_CONFIRMED_FACT"


def test_citation_validator_adds_info_when_official_position_uses_news_source() -> None:
    validator = CitationValidator()
    bullets = [
        ExplanationBullet(
            text="The agency argues its action is lawful.",
            source_ids=["news_1"],
            claim_label="official_position",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(bullets=bullets, sources=[make_news_source()])

    assert warnings[0].severity == "info"
    assert warnings[0].code == "OFFICIAL_POSITION_VIA_NEWS"


def test_citation_validator_accepts_public_statement_for_official_position() -> None:
    validator = CitationValidator()
    bullets = [
        ExplanationBullet(
            text="The organization supports the legislation.",
            source_ids=["statement_1"],
            claim_label="official_position",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(
        bullets=bullets,
        sources=[make_public_statement_source()],
    )

    assert warnings == []


def test_citation_validator_accepts_original_post_for_own_position() -> None:
    validator = CitationValidator()
    bullets = [
        ExplanationBullet(
            text="The author opposes privatizing public services.",
            source_ids=["thread_original"],
            claim_label="official_position",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(bullets=bullets, sources=[make_social_source()])

    assert warnings == []


def test_citation_validator_warns_when_author_interpretation_uses_thread_context() -> None:
    validator = CitationValidator()
    thread_context = Evidence(
        id="thread_context",
        title="Thread context",
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        snippet="Reply snippet.",
        content="Reply content.",
        source_type="social",
        source_category="social_post",
        source_role="public_reaction",
    )
    bullets = [
        ExplanationBullet(
            text="The author believes the issue is corrupt.",
            source_ids=["thread_context"],
            claim_label="author_interpretation",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(bullets=bullets, sources=[thread_context])

    assert warnings[0].code == "AUTHOR_INTERPRETATION_WITHOUT_ORIGINAL_POST"


def test_citation_validator_warns_when_sensitive_fact_uses_weak_source() -> None:
    validator = CitationValidator()
    bullets = [
        ExplanationBullet(
            text="The official was convicted of corruption.",
            source_ids=["s1"],
            claim_label="confirmed_fact",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(bullets=bullets, sources=[make_source()])

    assert warnings[0].code == "SENSITIVE_CLAIM_WITHOUT_STRONG_SOURCE"


def test_citation_validator_warns_when_portuguese_sensitive_fact_uses_weak_source() -> None:
    validator = CitationValidator()
    bullets = [
        ExplanationBullet(
            text="A investigação apura denúncia de desvio de recursos públicos.",
            source_ids=["s1"],
            claim_label="confirmed_fact",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(bullets=bullets, sources=[make_source()])

    assert warnings[0].code == "SENSITIVE_CLAIM_WITHOUT_STRONG_SOURCE"


def test_citation_validator_accepts_sensitive_fact_with_news_source() -> None:
    validator = CitationValidator()
    bullets = [
        ExplanationBullet(
            text="The official was convicted of corruption.",
            source_ids=["news_1"],
            claim_label="confirmed_fact",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(bullets=bullets, sources=[make_news_source()])

    assert warnings == []


def test_citation_validator_warns_when_public_reaction_uses_non_social_source() -> None:
    validator = CitationValidator()
    bullets = [
        ExplanationBullet(
            text="Readers reacted critically.",
            source_ids=["news_1"],
            claim_label="public_reaction",
        )
        for _ in range(3)
    ]

    warnings = validator.validate(bullets=bullets, sources=[make_news_source()])

    assert warnings[0].code == "PUBLIC_REACTION_WITHOUT_SOCIAL_SOURCE"


def test_response_schema_serializes_to_json() -> None:
    post = PostData(
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        platform="bluesky",
        author=PostAuthor(handle="example.bsky.social"),
        text="Post text",
        created_at=datetime(2026, 5, 14, tzinfo=UTC),
    )
    response = ExplanationResponse(
        post=post,
        explanation=[make_bullet() for _ in range(3)],
        sources=[make_source()],
        confidence="high",
        execution_time_ms=123,
    )

    payload = response.model_dump(mode="json")

    assert payload["post"]["url"] == "https://bsky.app/profile/example.bsky.social/post/abc"
    assert payload["execution_time_ms"] == 123


def test_eval_case_supports_expected_facts_and_forbidden_claims() -> None:
    case = EvalCase(
        id="tc01",
        description="Test case",
        post_fixture="fixtures/posts/tc01.json",
        evidence_fixture="fixtures/evidence/tc01.json",
        must_include_facts=["Expected fact"],
        must_not_claim=["Forbidden claim"],
    )

    assert case.requires_citations is True
    assert case.minimum_sources == 1
