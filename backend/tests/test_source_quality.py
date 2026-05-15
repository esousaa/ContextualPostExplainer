from datetime import UTC, datetime

from app.application.source_quality import evaluate_source_quality
from app.domain.models import Evidence, PostAuthor, PostData

LONG_CONTEXT = (
    "This article contains enough extractable reporting text to be used as a source. "
    "It includes the relevant timeline, actors, action, and context for a public event. "
    "The content is long enough for the quality filter to evaluate it as citation material."
)


def _post(text: str) -> PostData:
    return PostData(
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        platform="bluesky",
        author=PostAuthor(handle="example.bsky.social"),
        text=text,
        created_at=datetime(2026, 5, 15, tzinfo=UTC),
    )


def _evidence(content: str, published_at: datetime | None = None) -> Evidence:
    return Evidence(
        id="s1",
        title="Source",
        url="https://example.com/source",
        snippet="Useful snippet",
        content=content,
        source_type="web",
        published_at=published_at,
    )


def test_source_quality_uses_dynamic_event_anchors() -> None:
    post = _post("NASA announced a new Artemis Program milestone.")

    usable = evaluate_source_quality(
        post,
        _evidence(
            f"NASA announced a new Artemis Program milestone. {LONG_CONTEXT}",
            published_at=datetime(2026, 5, 14, tzinfo=UTC),
        ),
    )
    missing_anchor = evaluate_source_quality(
        post,
        _evidence(
            f"NASA issued a general operational update. {LONG_CONTEXT}",
            published_at=datetime(2026, 5, 14, tzinfo=UTC),
        ),
    )

    assert usable.usable is True
    assert missing_anchor.usable is False
    assert missing_anchor.reason == "missing_event_anchor"


def test_source_quality_filters_stale_sources() -> None:
    decision = evaluate_source_quality(
        _post("NASA announced a new Artemis Program milestone."),
        _evidence(
            f"NASA announced a new Artemis Program milestone. {LONG_CONTEXT}",
            published_at=datetime(2023, 1, 1, tzinfo=UTC),
        ),
    )

    assert decision.usable is False
    assert decision.reason == "stale_for_event"


def test_source_quality_allows_older_evergreen_place_sources() -> None:
    decision = evaluate_source_quality(
        _post("Puck’s Glen in the Argyll Forest Park, Scotland is spectacular."),
        _evidence(
            f"Puck's Glen is a woodland walk in Argyll Forest Park. {LONG_CONTEXT}",
            published_at=datetime(2020, 1, 1, tzinfo=UTC),
        ),
    )

    assert decision.usable is True


def test_source_quality_accepts_possessive_place_anchor() -> None:
    decision = evaluate_source_quality(
        _post("Puck’s Glen in the Argyll Forest Park, Scotland is spectacular."),
        _evidence(
            f"Puck's Glen is an attraction near Dunoon. {LONG_CONTEXT}",
            published_at=datetime(2020, 1, 1, tzinfo=UTC),
        ),
    )

    assert decision.usable is True


def test_source_quality_accepts_legislative_id_anchor() -> None:
    decision = evaluate_source_quality(
        _post("BREAKING: SB 2471 has been signed into law in Hawaii."),
        _evidence(
            f"SB 2471 was signed into law in Hawaii. {LONG_CONTEXT}",
            published_at=datetime(2026, 5, 14, tzinfo=UTC),
        ),
    )

    assert decision.usable is True


def test_source_quality_accepts_topic_anchor_from_possessive_event_phrase() -> None:
    decision = evaluate_source_quality(
        _post(
            "BREAKING: SB 2471 has been signed into law and renders the "
            "Supreme Court’s Citizens United decision irrelevant in Hawaii."
        ),
        _evidence(
            "Hawaii Legislature passes first-in-nation bill targeting Citizens "
            f"United ruling. {LONG_CONTEXT}",
            published_at=datetime(2026, 5, 14, tzinfo=UTC),
        ),
    )

    assert decision.usable is True


def test_source_quality_ignores_broad_geographic_anchor_for_opinion_posts() -> None:
    decision = evaluate_source_quality(
        _post(
            "Looking forward to the day this political figure is convicted "
            "for crimes against the United States."
        ),
        _evidence(
            f"Trump's criminal cases and charges are described here. {LONG_CONTEXT}",
            published_at=datetime(2025, 5, 14, tzinfo=UTC),
        ),
    )

    assert decision.usable is True
