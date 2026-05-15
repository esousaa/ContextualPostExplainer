from app.application.source_classification import classify_evidence
from app.domain.models import Evidence


def test_classifies_official_source() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="Official statement",
            url="https://www.justice.gov/opa/pr/example",
            snippet="Statement",
            content="Official source content.",
            source_type="web",
        )
    )

    assert source.publisher == "justice.gov"
    assert source.source_category == "primary_official"
    assert source.source_role == "official_position"


def test_classifies_news_source() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="News article",
            url="https://edition.cnn.com/2026/05/14/example",
            snippet="Article",
            content="News source content.",
            source_type="web",
        )
    )

    assert source.publisher == "edition.cnn.com"
    assert source.source_category == "news_outlet"
    assert source.source_role == "independent_context"


def test_classifies_abc_news_source() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="Poll story",
            url="https://abcnews.com/Politics/example",
            snippet="ABC News story.",
            content="News source content.",
            source_type="web",
        )
    )

    assert source.publisher == "abcnews.com"
    assert source.source_category == "news_outlet"
    assert source.source_role == "independent_context"


def test_classifies_local_news_source() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="Local news story",
            url="https://www.wral.com/story/example",
            snippet="Local news story.",
            content="News source content.",
            source_type="web",
        )
    )

    assert source.publisher == "wral.com"
    assert source.source_category == "news_outlet"
    assert source.source_role == "independent_context"


def test_classifies_manhattan_da_as_official_source() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="District attorney release",
            url="https://manhattanda.org/example",
            snippet="Official release.",
            content="Official source content.",
            source_type="web",
        )
    )

    assert source.publisher == "manhattanda.org"
    assert source.source_category == "primary_official"
    assert source.source_role == "official_position"


def test_classifies_brazilian_news_source() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="Brazilian news story",
            url="https://g1.globo.com/politica/noticia/example",
            snippet="News story.",
            content="News source content.",
            source_type="web",
        )
    )

    assert source.publisher == "g1.globo.com"
    assert source.source_category == "news_outlet"
    assert source.source_role == "independent_context"


def test_classifies_forbes_source() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="Forbes story",
            url="https://www.forbes.com/sites/example/story",
            snippet="Forbes story.",
            content="News source content.",
            source_type="web",
        )
    )

    assert source.publisher == "forbes.com"
    assert source.source_category == "news_outlet"
    assert source.source_role == "independent_context"


def test_classifies_thread_source_as_original_post() -> None:
    source = classify_evidence(
        Evidence(
            id="thread_original",
            title="Original post",
            url="https://bsky.app/profile/example.bsky.social/post/abc",
            snippet="Post",
            content="Post content.",
            source_type="thread",
        )
    )

    assert source.source_category == "social_post"
    assert source.source_role == "original_post"


def test_classifies_gov_scot_source() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="Puck's Glen",
            url="https://forestryandland.gov.scot/visit/forest-parks/argyll-forest-park/pucks-glen",
            snippet="Visitor information.",
            content="Visitor information for Puck's Glen.",
            source_type="web",
        )
    )

    assert source.publisher == "forestryandland.gov.scot"
    assert source.source_category == "primary_official"
    assert source.source_role == "official_position"


def test_classifies_public_statement_role_without_domain_allowlist() -> None:
    source = classify_evidence(
        Evidence(
            id="s1",
            title="Organization responds to legislation",
            url="https://example.org/press/example-legislation-response",
            snippet="The organization released the following statement.",
            content="Today, following the vote, the organization released a statement.",
            source_type="web",
        )
    )

    assert source.publisher == "example.org"
    assert source.source_category == "unknown"
    assert source.source_role == "official_position"
