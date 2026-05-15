import re
from dataclasses import dataclass

from app.application.image_context import image_context_text
from app.domain.deduplication import canonicalize_url
from app.domain.models import Evidence, PostData

MIN_WEB_CONTENT_CHARS = 200
STALE_SOURCE_DAYS = 370
MAX_REQUIRED_ANCHORS = 2
LEADING_ANCHOR_WORDS = {"a", "an", "the"}
IGNORED_ANCHOR_WORDS = {"breaking"}
BROAD_ANCHOR_PHRASES = {"united states"}
EVENT_SIGNAL_PATTERN = re.compile(
    r"\b("
    r"announced|breaking|charged|charges|court|election|filed|filing|indictment|"
    r"investigation|lawsuit|new|now|recent|report|reported|sued|sues|suing|"
    r"today|trial|vote|voted|yesterday"
    r")\b|\b20\d{2}\b",
    re.IGNORECASE,
)
LEGISLATIVE_ID_PATTERN = re.compile(
    r"\b(?:SB|HB|AB|HR|S|H\.R\.)\s*[-.]?\s*\d+[A-Za-z]?\b"
)
ENTITY_PHRASE_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,}|[A-Z][a-z]+)(?:['’]s)?"
    r"(?:\s+(?:[A-Z]{2,}|[A-Z][a-z]+)(?:['’]s)?)+\b"
)


@dataclass(frozen=True)
class SourceQualityDecision:
    usable: bool
    reason: str | None = None


def evaluate_source_quality(post: PostData, evidence: Evidence) -> SourceQualityDecision:
    if evidence.source_type in {"thread", "social", "fixture", "image"}:
        return SourceQualityDecision(usable=True)

    if len(evidence.content) < MIN_WEB_CONTENT_CHARS:
        return SourceQualityDecision(usable=False, reason="insufficient_extractable_text")

    if _requires_recent_sources(post) and _is_stale_for_post(post, evidence):
        return SourceQualityDecision(usable=False, reason="stale_for_event")

    if not _matches_required_event_anchors(post, evidence):
        return SourceQualityDecision(usable=False, reason="missing_event_anchor")

    return SourceQualityDecision(usable=True)


def _is_stale_for_post(post: PostData, evidence: Evidence) -> bool:
    if not post.created_at or not evidence.published_at:
        return False

    if evidence.url and matches_post_link(post, evidence.url.unicode_string()):
        return False

    post_date = post.created_at.date()
    evidence_date = evidence.published_at.date()
    return (post_date - evidence_date).days > STALE_SOURCE_DAYS


def _matches_required_event_anchors(post: PostData, evidence: Evidence) -> bool:
    anchors = _required_event_anchors(_event_anchor_text(post))
    if not anchors:
        return True

    evidence_text = _normalize_anchor_text(_evidence_text(evidence))
    return any(any(variant in evidence_text for variant in variants) for variants in anchors)


def _required_event_anchors(post_text: str) -> list[tuple[str, ...]]:
    candidates: list[tuple[int, str, tuple[str, ...]]] = []
    seen: set[str] = set()

    for match in LEGISLATIVE_ID_PATTERN.finditer(post_text):
        phrase = match.group(0)
        normalized = _normalize_anchor_text(phrase)
        candidates.append((0, normalized, _anchor_variants(phrase)))
        seen.add(normalized)

    for match in ENTITY_PHRASE_PATTERN.finditer(post_text):
        raw_phrase = match.group(0)
        for phrase in _anchor_phrases(raw_phrase):
            normalized = _normalize_anchor_text(phrase)
            if not _is_anchor_candidate(normalized):
                continue
            if normalized in seen:
                continue

            candidates.append((_anchor_priority(phrase), normalized, _anchor_variants(phrase)))
            seen.add(normalized)

    if not candidates:
        return []

    ordered = sorted(candidates, key=lambda item: (item[0], len(item[1])))
    return [variants for _, _, variants in ordered[:MAX_REQUIRED_ANCHORS]]


def _event_anchor_text(post: PostData) -> str:
    parts = [post.text, post.parent_text, post.quote_text, image_context_text(post)]
    return "\n\n".join(part for part in parts if part)


def _evidence_text(evidence: Evidence) -> str:
    return "\n\n".join(
        [
            evidence.title,
            evidence.snippet,
            evidence.content,
            evidence.url.unicode_string() if evidence.url else "",
        ]
    )


def _requires_recent_sources(post: PostData) -> bool:
    return bool(EVENT_SIGNAL_PATTERN.search(_event_anchor_text(post)))


def matches_post_link(post: PostData, evidence_url: str) -> bool:
    evidence_canonical = canonicalize_url(evidence_url)
    return any(canonicalize_url(link.unicode_string()) == evidence_canonical for link in post.links)


def _anchor_phrases(phrase: str) -> list[str]:
    cleaned = _clean_anchor_phrase(phrase)
    phrases = [cleaned]
    if "'s" in cleaned.lower() or "’s" in cleaned.lower():
        split_parts = re.split(r"\b[^ ]+['’]s\s+", cleaned, maxsplit=1)
        if len(split_parts) == 2 and split_parts[1].strip():
            phrases.insert(0, split_parts[1].strip())
    return phrases


def _clean_anchor_phrase(phrase: str) -> str:
    tokens = phrase.split()
    while tokens and tokens[0].lower() in LEADING_ANCHOR_WORDS | IGNORED_ANCHOR_WORDS:
        tokens = tokens[1:]
    return " ".join(tokens)


def _is_anchor_candidate(normalized_phrase: str) -> bool:
    tokens = normalized_phrase.split()
    if len(tokens) < 2:
        return False
    if normalized_phrase in BROAD_ANCHOR_PHRASES:
        return False
    if all(token in IGNORED_ANCHOR_WORDS for token in tokens):
        return False
    return True


def _anchor_priority(phrase: str) -> int:
    return 0 if any(_is_acronym_token(token) for token in phrase.split()) else 1


def _anchor_variants(phrase: str) -> tuple[str, ...]:
    normalized = _normalize_anchor_text(phrase)
    variants = {normalized}
    tokens = phrase.split()

    for index, token in enumerate(tokens):
        if _is_acronym_token(token):
            stripped = re.sub(r"[^A-Za-z]", "", token)
            dotted = ".".join(stripped.lower()) + "."
            variant_tokens = [*tokens]
            variant_tokens[index] = dotted
            variants.add(_normalize_anchor_text(" ".join(variant_tokens)))

    return tuple(sorted(variants))


def _is_acronym_token(token: str) -> bool:
    stripped = re.sub(r"[^A-Za-z]", "", token)
    return len(stripped) > 1 and stripped.isupper()


def _normalize_anchor_text(text: str) -> str:
    normalized = text.lower().replace("’", "'")
    normalized = re.sub(r"(?<=\w)'s\b", "s", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()
