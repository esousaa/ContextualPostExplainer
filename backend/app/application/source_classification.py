from urllib.parse import urlparse

from app.domain.models import Evidence, SourceCategory, SourceRole

OFFICIAL_DOMAIN_SUFFIXES = (
    ".gov",
    ".gov.scot",
    ".gov.uk",
    ".gov.br",
    ".jus.br",
    ".leg.br",
    ".mil",
    ".edu",
    ".judiciary.uk",
)
COURT_DOMAINS = (
    "courtlistener.com",
    "law.justia.com",
    "supremecourt.gov",
    "uscourts.gov",
)
OFFICIAL_DOMAINS = (
    "manhattanda.org",
)
KNOWN_NEWS_DOMAINS = (
    "abajournal.com",
    "abcnews.com",
    "abcnews.go.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "bloomberg.com",
    "bloomberglaw.com",
    "civilbeat.org",
    "cnn.com",
    "courthousenews.com",
    "devdiscourse.com",
    "forbes.com",
    "g1.globo.com",
    "globo.com",
    "gpb.org",
    "iclnoticias.com.br",
    "imirante.com",
    "jornalggn.com.br",
    "ktla.com",
    "ms.now",
    "minnlawyer.com",
    "mynbc15.com",
    "nbcnews.com",
    "newsweek.com",
    "npr.org",
    "nypost.com",
    "opb.org",
    "nytimes.com",
    "pbs.org",
    "reporter-times.com",
    "reuters.com",
    "riotimesonline.com",
    "spectrumlocalnews.com",
    "tmc.com.br",
    "theguardian.com",
    "thehill.com",
    "trtworld.com",
    "uol.com.br",
    "usnews.com",
    "valorinternational.globo.com",
    "washingtonpost.com",
    "wral.com",
    "wtop.com",
    "yahoo.com",
)
FACT_CHECKING_DOMAINS = (
    "factcheck.org",
    "politifact.com",
    "snopes.com",
)
SOCIAL_DOMAINS = (
    "bsky.app",
    "facebook.com",
    "instagram.com",
    "mastodon.social",
    "reddit.com",
    "threads.net",
    "twitter.com",
    "x.com",
)
PUBLIC_STATEMENT_PATH_SEGMENTS = {
    "newsroom",
    "press",
    "press-release",
    "press-releases",
    "statement",
    "statements",
}


def classify_evidence(evidence: Evidence) -> Evidence:
    category = classify_source_category(evidence)
    role = classify_source_role(evidence, category)
    publisher = evidence.publisher or _publisher_from_url(evidence)
    return evidence.model_copy(
        update={
            "publisher": publisher,
            "source_category": category,
            "source_role": role,
        }
    )


def classify_source_category(evidence: Evidence) -> SourceCategory:
    if evidence.source_type == "image":
        return "unknown"
    if evidence.source_type == "thread":
        return "social_post"
    if evidence.source_type == "social":
        return "social_post"

    domain = _domain(evidence)
    if not domain:
        return "unknown"

    if _domain_matches(domain, SOCIAL_DOMAINS):
        return "social_post"
    if _domain_matches(domain, COURT_DOMAINS):
        return "court_document"
    if _domain_matches(domain, OFFICIAL_DOMAINS):
        return "primary_official"
    if any(domain.endswith(suffix) for suffix in OFFICIAL_DOMAIN_SUFFIXES):
        return "primary_official"
    if _domain_matches(domain, FACT_CHECKING_DOMAINS):
        return "fact_checking"
    if _domain_matches(domain, KNOWN_NEWS_DOMAINS):
        return "news_outlet"
    return "unknown"


def classify_source_role(evidence: Evidence, category: SourceCategory) -> SourceRole:
    if evidence.source_type == "image":
        return "image_observation"
    if evidence.source_type == "thread":
        return "original_post"
    if category == "social_post":
        return "public_reaction"
    if category == "primary_official":
        return "official_position"
    if category == "court_document":
        return "primary_evidence"
    if category in {"news_outlet", "fact_checking"}:
        return "independent_context"
    if _looks_like_public_statement(evidence):
        return "official_position"
    return "background_support"


def _publisher_from_url(evidence: Evidence) -> str | None:
    domain = _domain(evidence)
    return domain if domain else None


def _domain(evidence: Evidence) -> str:
    if not evidence.url:
        return ""
    host = urlparse(evidence.url.unicode_string()).netloc.lower()
    return host.removeprefix("www.")


def _domain_matches(domain: str, known_domains: tuple[str, ...]) -> bool:
    return any(domain == known or domain.endswith(f".{known}") for known in known_domains)


def _looks_like_public_statement(evidence: Evidence) -> bool:
    if not evidence.url:
        return False

    path_segments = {
        segment.lower()
        for segment in urlparse(evidence.url.unicode_string()).path.split("/")
        if segment
    }
    if path_segments.intersection(PUBLIC_STATEMENT_PATH_SEGMENTS):
        return True

    statement_text = " ".join([evidence.title, evidence.snippet, evidence.content]).lower()
    return "released the following statement" in statement_text
