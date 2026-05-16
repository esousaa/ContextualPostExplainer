from app.domain.errors import CitationValidationError
from app.domain.models import Evidence, Explanation, PostData, ValidationWarning
from app.domain.validation import (
    CRITICAL_WARNING_CODES,
    CitationValidator,
    has_critical_warnings,
)
from app.ports.llm_client import LLMClient

CRITICAL_WARNING_EXPLANATIONS = {
    "AUTHOR_INTERPRETATION_WITHOUT_ORIGINAL_POST": (
        "author interpretation was not cited to the original post"
    ),
    "OFFICIAL_POSITION_WITHOUT_PRIMARY_SOURCE": (
        "official-position claims lacked an official, primary, court, or recognized news source"
    ),
    "PUBLIC_REACTION_WITHOUT_SOCIAL_SOURCE": (
        "public-reaction claims were not cited to thread or social sources"
    ),
    "SENSITIVE_CLAIM_WITHOUT_STRONG_SOURCE": (
        "sensitive factual claims lacked official, court, fact-checking, or recognized news support"
    ),
    "SOCIAL_ONLY_CONFIRMED_FACT": (
        "confirmed factual claims were supported only by social or thread sources"
    ),
}


def validate_citation_contract(
    explanation: Explanation,
    evidence: list[Evidence],
    citation_validator: CitationValidator,
) -> dict[str, object]:
    try:
        validation_warnings = citation_validator.validate(explanation.bullets, evidence)
    except CitationValidationError as exc:
        return {
            "needs_repair": True,
            "validation_error": exc.message,
            "validation_warnings": [],
        }

    if has_critical_warnings(validation_warnings):
        return {
            "needs_repair": True,
            "validation_error": _format_validation_warnings(validation_warnings),
            "validation_warnings": validation_warnings,
        }

    return {
        "needs_repair": False,
        "validation_error": None,
        "validation_warnings": validation_warnings,
        "explanation": _with_validation_warnings(explanation, validation_warnings),
    }


async def repair_citation_contract_once(
    *,
    post: PostData,
    evidence: list[Evidence],
    explanation: Explanation,
    validation_error: str | None,
    validation_warnings: list[ValidationWarning],
    llm_client: LLMClient,
    citation_validator: CitationValidator,
) -> dict[str, object]:
    if not validation_error and not has_critical_warnings(validation_warnings):
        return {}

    repaired = await llm_client.repair_explanation(
        post=post,
        evidence=evidence,
        invalid_payload=explanation.model_dump_json(),
        validation_error=validation_error or _format_validation_warnings(validation_warnings),
    )

    try:
        repaired_warnings = citation_validator.validate(repaired.bullets, evidence)
    except CitationValidationError:
        return _failed_repair_result()

    if not has_critical_warnings(repaired_warnings):
        return {
            "explanation": _with_validation_warnings(repaired, repaired_warnings),
            "needs_repair": False,
            "validation_error": None,
            "validation_warnings": repaired_warnings,
        }

    hardened = _remove_critical_bullets(repaired, repaired_warnings)
    try:
        hardened_warnings = citation_validator.validate(hardened.bullets, evidence)
    except CitationValidationError:
        return _failed_repair_result()

    return {
        "explanation": _with_validation_warnings(hardened, hardened_warnings),
        "needs_repair": False,
        "validation_error": None,
        "validation_warnings": hardened_warnings,
    }


def _with_validation_warnings(
    explanation: Explanation,
    validation_warnings: list[ValidationWarning],
) -> Explanation:
    if not validation_warnings:
        return explanation
    new_warnings = [
        warning for warning in validation_warnings if warning not in explanation.warnings
    ]
    if not new_warnings:
        return explanation
    return explanation.model_copy(update={"warnings": [*explanation.warnings, *new_warnings]})


def _format_validation_warnings(warnings: list[ValidationWarning]) -> str:
    formatted = [
        f"{warning.code} on bullet {warning.bullet_index}: {warning.message}"
        for warning in warnings
    ]
    return (
        "Return a corrected response that removes, reclassifies, or recites bullets "
        "so these citation compatibility warnings are resolved: " + " | ".join(formatted)
    )


def _remove_critical_bullets(
    explanation: Explanation,
    warnings: list[ValidationWarning],
) -> Explanation:
    critical_indices = {
        warning.bullet_index
        for warning in warnings
        if warning.code in CRITICAL_WARNING_CODES and warning.bullet_index is not None
    }
    bullets = [
        bullet for index, bullet in enumerate(explanation.bullets) if index not in critical_indices
    ]
    warning = _critical_bullets_removed_warning(warnings)

    if len(bullets) < 3:
        return Explanation(
            bullets=[],
            confidence="low",
            warnings=[warning],
        )

    confidence = "medium" if explanation.confidence == "high" else explanation.confidence
    return explanation.model_copy(
        update={
            "bullets": bullets,
            "confidence": confidence,
            "warnings": [*explanation.warnings, warning],
        }
    )


def _failed_repair_result() -> dict[str, object]:
    return {
        "explanation": Explanation(
            bullets=[],
            confidence="low",
            warnings=[
                "Insufficient evidence to generate a reliable explanation.",
                "The generated explanation failed citation validation after repair.",
                "No explanatory bullets were generated to avoid unsupported claims.",
            ],
        ),
        "needs_repair": False,
        "validation_error": None,
        "validation_warnings": [],
    }


def _critical_bullets_removed_warning(warnings: list[ValidationWarning]) -> ValidationWarning:
    critical_reasons = [
        CRITICAL_WARNING_EXPLANATIONS[warning.code]
        for warning in warnings
        if warning.code in CRITICAL_WARNING_EXPLANATIONS
    ]
    message = (
        "Unsupported bullets were removed because their citations did not match the claim type."
    )
    if critical_reasons:
        message += " Reasons: " + "; ".join(sorted(set(critical_reasons))) + "."
    return ValidationWarning(
        severity="warning",
        code="CRITICAL_BULLETS_REMOVED",
        message=message,
    )
