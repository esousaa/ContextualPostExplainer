import re

from app.application.image_evidence_builder import image_context_text
from app.domain.models import PostData

MAX_LIVE_QUERIES = 6
IGNORED_NAME_TOKENS = {"If", "Looking", "This", "United", "States"}
LEGISLATIVE_ID_PATTERN = re.compile(r"\b(?:SB|HB|AB|HR|S|H\.R\.)\s*[-.]?\s*\d+[A-Za-z]?\b")
SIGNED_INTO_LAW_PATTERN = re.compile(
    r"\b(signed\s+into\s+law|enacted|became\s+law)\b",
    re.IGNORECASE,
)
LEGAL_ACCOUNTABILITY_PATTERN = re.compile(
    r"\b(arrested|charges?|convicted|criminal|felon|incarcerated|indicted|"
    r"prison|prosecuted|sentenced|trial)\b",
    re.IGNORECASE,
)
NAME_PATTERN = re.compile(r"\b([A-Z][a-z]{2,})(?:['’]s)?\b")
ENTITY_PHRASE_PATTERN = re.compile(
    r"\b(?:[A-Z]{2,}|[A-Z][a-z]+)(?:['’]s)?"
    r"(?:\s+(?:[A-Z]{2,}|[A-Z][a-z]+)(?:['’]s)?)+\b"
)


def augment_live_queries(post: PostData, llm_queries: list[str]) -> list[str]:
    query_candidates = [*_deterministic_queries(post), *llm_queries]
    queries: list[str] = []
    seen: set[str] = set()

    for query in query_candidates:
        normalized = _normalize_query(query)
        if not normalized or normalized in seen:
            continue
        queries.append(query.strip())
        seen.add(normalized)
        if len(queries) == MAX_LIVE_QUERIES:
            break

    return queries


def _deterministic_queries(post: PostData) -> list[str]:
    text = _post_context(post)
    legislative_ids = _legislative_ids(text)
    entities = _entity_phrases(text)
    queries = _legal_accountability_queries(text)

    for legislative_id in legislative_ids:
        if SIGNED_INTO_LAW_PATTERN.search(text):
            queries.extend(
                [
                    f"{legislative_id} signed into law",
                    f"{legislative_id} governor",
                ]
            )
        for entity in entities[:2]:
            queries.append(f"{legislative_id} {entity}")

    return queries


def _post_context(post: PostData) -> str:
    parts = [
        post.text,
        post.parent_text,
        post.quote_text,
        post.thread_text,
        image_context_text(post),
    ]
    return "\n\n".join(part for part in parts if part)


def _legislative_ids(text: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for match in LEGISLATIVE_ID_PATTERN.finditer(text):
        legislative_id = re.sub(r"\s+", " ", match.group(0).replace(".", " ")).strip()
        normalized = _normalize_query(legislative_id)
        if normalized in seen:
            continue
        ids.append(legislative_id)
        seen.add(normalized)
    return ids


def _entity_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    seen: set[str] = set()
    for match in ENTITY_PHRASE_PATTERN.finditer(text):
        phrase = _clean_entity_phrase(match.group(0))
        normalized = _normalize_query(phrase)
        if len(normalized.split()) < 2 or normalized in seen:
            continue
        phrases.append(phrase)
        seen.add(normalized)
    return phrases


def _legal_accountability_queries(text: str) -> list[str]:
    if not LEGAL_ACCOUNTABILITY_PATTERN.search(text):
        return []

    queries: list[str] = []
    seen: set[str] = set()
    for name in _names_nearest_legal_terms(text):
        normalized_name = _normalize_query(name)
        if normalized_name in seen:
            continue
        seen.add(normalized_name)
        queries.extend(
            [
                f"{name} criminal charges conviction",
                f"{name} legal cases status",
            ]
        )
        if len(queries) >= 4:
            break

    return queries


def _names_nearest_legal_terms(text: str) -> list[str]:
    names: list[str] = []
    for sentence in re.split(r"[.!?]\s+", text):
        for legal_match in LEGAL_ACCOUNTABILITY_PATTERN.finditer(sentence):
            preceding_names = list(NAME_PATTERN.finditer(sentence[: legal_match.start()]))
            if not preceding_names:
                continue
            name = preceding_names[-1].group(1)
            if name in IGNORED_NAME_TOKENS:
                continue
            names.append(name)
    return names


def _clean_entity_phrase(phrase: str) -> str:
    cleaned = phrase.replace("’", "'")
    if "'s " in cleaned:
        cleaned = cleaned.split("'s ", maxsplit=1)[1]
    return cleaned.strip()


def _normalize_query(query: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower())
    return re.sub(r"\s+", " ", normalized).strip()
