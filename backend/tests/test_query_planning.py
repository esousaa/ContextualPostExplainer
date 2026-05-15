from datetime import UTC, datetime

from app.application.query_planning import augment_live_queries
from app.domain.models import PostAuthor, PostData


def _post(text: str) -> PostData:
    return PostData(
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        platform="bluesky",
        author=PostAuthor(handle="example.bsky.social"),
        text=text,
        created_at=datetime(2026, 5, 15, tzinfo=UTC),
    )


def test_augment_live_queries_adds_legislative_signature_queries() -> None:
    queries = augment_live_queries(
        _post(
            "BREAKING: SB 2471 has been signed into law and renders the "
            "Supreme Court’s Citizens United decision irrelevant in Hawaii."
        ),
        ["Citizens United Supreme Court decision"],
    )

    assert queries[:3] == [
        "SB 2471 signed into law",
        "SB 2471 governor",
        "SB 2471 Citizens United",
    ]
    assert "Citizens United Supreme Court decision" in queries


def test_augment_live_queries_deduplicates_normalized_queries() -> None:
    queries = augment_live_queries(
        _post("SB 2471 has been signed into law."),
        ["sb-2471 signed into law", "SB 2471 signed into law"],
    )

    assert queries.count("SB 2471 signed into law") == 1


def test_augment_live_queries_adds_legal_accountability_queries_for_named_context() -> None:
    post = _post("Looking forward to future convictions for crimes.")
    post = post.model_copy(
        update={
            "thread_text": (
                "If Kamala Harris had become president, Trump's case would have "
                "led to him getting incarcerated."
            )
        }
    )

    queries = augment_live_queries(post, ["orange felon arrest"])

    assert queries[:2] == [
        "Trump criminal charges conviction",
        "Trump legal cases status",
    ]
    assert "orange felon arrest" in queries
    assert "Looking criminal charges conviction" not in queries
