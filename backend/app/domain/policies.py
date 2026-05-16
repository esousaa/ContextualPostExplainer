from app.domain.errors import CitationValidationError
from app.domain.models import Evidence, ExplanationBullet

MIN_EXPLANATION_BULLETS = 3
MAX_EXPLANATION_BULLETS = 5
CITABLE_SOURCE_TYPES_WITHOUT_URL = {"thread", "fixture", "image"}


def validate_explanation_size(bullets: list[ExplanationBullet]) -> None:
    if not bullets:
        return

    if not MIN_EXPLANATION_BULLETS <= len(bullets) <= MAX_EXPLANATION_BULLETS:
        raise CitationValidationError(
            "Explanation must contain 3 to 5 bullets, or no bullets when evidence is insufficient."
        )


def validate_source_references(
    bullets: list[ExplanationBullet],
    sources: list[Evidence],
) -> None:
    source_ids = {source.id for source in sources}

    for bullet in bullets:
        missing_ids = [source_id for source_id in bullet.source_ids if source_id not in source_ids]
        if missing_ids:
            raise CitationValidationError(
                f"Bullet references unknown source ids: {', '.join(missing_ids)}."
            )


def validate_citable_sources(sources: list[Evidence]) -> None:
    for source in sources:
        if source.url is None and source.source_type not in CITABLE_SOURCE_TYPES_WITHOUT_URL:
            raise CitationValidationError(f"Source {source.id} is not citable.")
