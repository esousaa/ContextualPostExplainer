from app.domain.models import Evidence, ExplanationBullet, ValidationWarning
from app.domain.policies import (
    validate_citable_sources,
    validate_explanation_size,
    validate_source_references,
)

CRITICAL_WARNING_CODES = {
    "AUTHOR_INTERPRETATION_WITHOUT_ORIGINAL_POST",
    "OFFICIAL_POSITION_WITHOUT_PRIMARY_SOURCE",
    "PUBLIC_REACTION_WITHOUT_SOCIAL_SOURCE",
    "SENSITIVE_CLAIM_WITHOUT_STRONG_SOURCE",
    "SOCIAL_ONLY_CONFIRMED_FACT",
}
SENSITIVE_CLAIM_TERMS = (
    "accepted",
    "arrest",
    "bribe",
    "bribery",
    "charged",
    "convicted",
    "corrupt",
    "corruption",
    "crime",
    "criminal",
    "corrup",
    "acus",
    "denúncia",
    "denuncia",
    "desvio",
    "disbarment",
    "felony",
    "fraud",
    "indict",
    "investiga",
    "investigation",
    "lawsuit",
    "misuse",
    "probe",
    "propina",
    "processo",
    "prosecution",
)
STRONG_FACT_CATEGORIES = {
    "court_document",
    "fact_checking",
    "news_outlet",
    "primary_official",
}
STRONG_FACT_ROLES = {
    "official_position",
    "primary_evidence",
}


class CitationValidator:
    def validate(
        self,
        bullets: list[ExplanationBullet],
        sources: list[Evidence],
    ) -> list[ValidationWarning]:
        validate_explanation_size(bullets)
        validate_citable_sources(sources)
        validate_source_references(bullets, sources)
        return _validate_source_compatibility(bullets, sources)


def _validate_source_compatibility(
    bullets: list[ExplanationBullet],
    sources: list[Evidence],
) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    sources_by_id = {source.id: source for source in sources}

    for index, bullet in enumerate(bullets):
        cited_sources = [sources_by_id[source_id] for source_id in bullet.source_ids]
        source_categories = {source.source_category for source in cited_sources}
        source_roles = {source.source_role for source in cited_sources}

        if bullet.claim_label == "confirmed_fact" and source_categories.issubset(
            {"social_post", "thread_comment"}
        ):
            warnings.append(
                ValidationWarning(
                    severity="warning",
                    code="SOCIAL_ONLY_CONFIRMED_FACT",
                    message=(
                        "Confirmed factual claim is supported only by social media "
                        "or thread sources."
                    ),
                    bullet_index=index,
                )
            )

        if (
            bullet.claim_label == "confirmed_fact"
            and _contains_sensitive_claim(bullet.text)
            and not _has_strong_fact_source(source_categories, source_roles)
        ):
            warnings.append(
                ValidationWarning(
                    severity="warning",
                    code="SENSITIVE_CLAIM_WITHOUT_STRONG_SOURCE",
                    message=(
                        "Sensitive factual claim is not supported by an official, "
                        "court, fact-checking, or recognized news source."
                    ),
                    bullet_index=index,
                )
            )

        if bullet.claim_label == "official_position":
            has_primary = bool(
                source_categories.intersection({"primary_official", "court_document"})
                or source_roles.intersection(
                    {"official_position", "original_post", "primary_evidence"}
                )
            )
            has_news = "news_outlet" in source_categories
            if not has_primary and not has_news:
                warnings.append(
                    ValidationWarning(
                        severity="warning",
                        code="OFFICIAL_POSITION_WITHOUT_PRIMARY_SOURCE",
                        message=(
                            "Official position is not supported by an official source, "
                            "primary document, or recognized news outlet."
                        ),
                        bullet_index=index,
                    )
                )
            elif not has_primary and has_news:
                warnings.append(
                    ValidationWarning(
                        severity="info",
                        code="OFFICIAL_POSITION_VIA_NEWS",
                        message=(
                            "Official position is supported by a news outlet report "
                            "rather than a primary source."
                        ),
                        bullet_index=index,
                    )
                )

        if bullet.claim_label == "author_interpretation" and "original_post" not in source_roles:
            warnings.append(
                ValidationWarning(
                    severity="warning",
                    code="AUTHOR_INTERPRETATION_WITHOUT_ORIGINAL_POST",
                    message=(
                        "Author interpretation should be supported by the original "
                        "post, not by third-party thread context."
                    ),
                    bullet_index=index,
                )
            )

        if bullet.claim_label == "public_reaction" and not source_categories.intersection(
            {"social_post", "thread_comment"}
        ):
            warnings.append(
                ValidationWarning(
                    severity="warning",
                    code="PUBLIC_REACTION_WITHOUT_SOCIAL_SOURCE",
                    message=(
                        "Public reaction should be supported by thread comments "
                        "or social sources."
                    ),
                    bullet_index=index,
                )
            )

    return warnings


def has_critical_warnings(warnings: list[ValidationWarning]) -> bool:
    return any(warning.code in CRITICAL_WARNING_CODES for warning in warnings)


def _contains_sensitive_claim(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in SENSITIVE_CLAIM_TERMS)


def _has_strong_fact_source(
    source_categories: set[str],
    source_roles: set[str],
) -> bool:
    return bool(
        source_categories.intersection(STRONG_FACT_CATEGORIES)
        or source_roles.intersection(STRONG_FACT_ROLES)
    )
