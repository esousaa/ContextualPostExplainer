from app.domain.errors import CitationValidationError
from app.domain.models import Evidence, Explanation, PostData, RankedEvidence, ValidationWarning
from app.domain.validation import (
    CRITICAL_WARNING_CODES,
    CitationValidator,
    has_critical_warnings,
)
from app.ports.llm_client import LLMClient


class ExplanationGenerator:
    def __init__(
        self,
        llm_client: LLMClient,
        citation_validator: CitationValidator | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._citation_validator = citation_validator or CitationValidator()

    async def generate(
        self,
        post: PostData,
        evidence: list[RankedEvidence] | list[Evidence],
    ) -> Explanation:
        if not evidence:
            return Explanation(
                bullets=[],
                confidence="low",
                warnings=[
                    "Insufficient evidence to generate a reliable explanation.",
                    "No explanatory bullets were generated to avoid unsupported claims.",
                ],
            )

        explanation = await self._llm_client.generate_explanation(post, list(evidence))

        return await self._validate_repair_or_harden(post, list(evidence), explanation)


    async def _validate_repair_or_harden(
        self,
        post: PostData,
        evidence: list[Evidence],
        explanation: Explanation,
    ) -> Explanation:
        try:
            validation_warnings = self._citation_validator.validate(
                explanation.bullets,
                evidence,
            )
        except CitationValidationError as exc:
            return await self._repair_after_failure(
                post=post,
                evidence=evidence,
                explanation=explanation,
                validation_error=exc.message,
            )

        if not has_critical_warnings(validation_warnings):
            return _with_validation_warnings(explanation, validation_warnings)

        repaired = await self._llm_client.repair_explanation(
            post=post,
            evidence=evidence,
            invalid_payload=explanation.model_dump_json(),
            validation_error=_format_validation_warnings(validation_warnings),
        )
        try:
            repaired_warnings = self._citation_validator.validate(
                repaired.bullets,
                evidence,
            )
        except CitationValidationError as exc:
            return await self._repair_after_failure(
                post=post,
                evidence=evidence,
                explanation=repaired,
                validation_error=exc.message,
            )

        if not has_critical_warnings(repaired_warnings):
            return _with_validation_warnings(repaired, repaired_warnings)

        hardened = _remove_critical_bullets(repaired, repaired_warnings)
        try:
            hardened_warnings = self._citation_validator.validate(
                hardened.bullets,
                evidence,
            )
        except CitationValidationError:
            return _empty_after_failed_repair()

        return _with_validation_warnings(hardened, hardened_warnings)

    async def _repair_after_failure(
        self,
        post: PostData,
        evidence: list[Evidence],
        explanation: Explanation,
        validation_error: str,
    ) -> Explanation:
        repaired = await self._llm_client.repair_explanation(
            post=post,
            evidence=evidence,
            invalid_payload=explanation.model_dump_json(),
            validation_error=validation_error,
        )

        try:
            validation_warnings = self._citation_validator.validate(
                repaired.bullets,
                evidence,
            )
        except CitationValidationError:
            return _empty_after_failed_repair()

        if has_critical_warnings(validation_warnings):
            hardened = _remove_critical_bullets(repaired, validation_warnings)
            try:
                hardened_warnings = self._citation_validator.validate(
                    hardened.bullets,
                    evidence,
                )
            except CitationValidationError:
                return _empty_after_failed_repair()
            return _with_validation_warnings(hardened, hardened_warnings)

        return _with_validation_warnings(repaired, validation_warnings)


def _with_validation_warnings(
    explanation: Explanation,
    validation_warnings: list[ValidationWarning],
) -> Explanation:
    if not validation_warnings:
        return explanation
    return explanation.model_copy(
        update={"warnings": [*explanation.warnings, *validation_warnings]}
    )


def _format_validation_warnings(warnings: list[ValidationWarning]) -> str:
    formatted = [
        f"{warning.code} on bullet {warning.bullet_index}: {warning.message}"
        for warning in warnings
    ]
    return (
        "Return a corrected response that removes, reclassifies, or recites bullets "
        "so these citation compatibility warnings are resolved: "
        + " | ".join(formatted)
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
    warning = ValidationWarning(
        severity="warning",
        code="CRITICAL_BULLETS_REMOVED",
        message=(
            "Unsupported bullets were removed because they failed citation "
            "compatibility checks."
        ),
    )

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


def _empty_after_failed_repair() -> Explanation:
    return Explanation(
        bullets=[],
        confidence="low",
        warnings=[
            "Insufficient evidence to generate a reliable explanation.",
            "The generated explanation failed citation validation after repair.",
            "No explanatory bullets were generated to avoid unsupported claims.",
        ],
    )
