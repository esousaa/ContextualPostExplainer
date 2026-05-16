from math import isfinite

import numpy as np

from app.application.image_context import image_context_text
from app.application.source_quality import evaluate_source_quality, matches_post_link
from app.domain.models import Evidence, PostData, RankedEvidence
from app.ports.embedding_client import EmbeddingClient

MAX_EMBEDDING_TEXT_CHARS = 3_000


class EvidenceRanker:
    def __init__(self, embedding_client: EmbeddingClient) -> None:
        self._embedding_client = embedding_client

    async def rank(
        self,
        post: PostData,
        evidence: list[Evidence],
        top_n: int = 8,
    ) -> list[RankedEvidence]:
        if not evidence:
            return []

        candidates = [item for item in evidence if _is_candidate(post, item)]
        if not candidates:
            return []

        texts = [_post_text(post), *[_evidence_text(item) for item in candidates]]
        vectors = await self._embedding_client.embed(texts)
        if len(vectors) != len(texts):
            return []

        post_vector = np.array(vectors[0], dtype=float)
        ranked: list[RankedEvidence] = []
        for item, vector in zip(candidates, vectors[1:], strict=True):
            similarity = _cosine_similarity(post_vector, np.array(vector, dtype=float))
            score = max(0.0, similarity + _boost(post, item))
            ranked.append(
                RankedEvidence(
                    **item.model_dump(mode="json"),
                    relevance_score=score,
                )
            )

        ranked.sort(key=lambda item: item.relevance_score, reverse=True)
        return ranked[:top_n]


def _post_text(post: PostData) -> str:
    parts = [
        post.text,
        post.parent_text,
        post.quote_text,
        post.thread_text,
        image_context_text(post),
    ]
    return _truncate_embedding_text("\n\n".join(part for part in parts if part))


def _evidence_text(evidence: Evidence) -> str:
    return _truncate_embedding_text(
        "\n\n".join([evidence.title, evidence.snippet, evidence.content])
    )


def _truncate_embedding_text(text: str) -> str:
    normalized = " ".join(text.split())
    return normalized[:MAX_EMBEDDING_TEXT_CHARS]


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0.0:
        return 0.0

    score = float(np.dot(left, right) / denominator)
    return score if isfinite(score) else 0.0


def _boost(post: PostData, evidence: Evidence) -> float:
    score = 0.0
    if evidence.source_type in {"thread", "social"}:
        score += 0.05
    if len(evidence.content) >= 1000:
        score += 0.03
    if evidence.provider_result_count > 1 or len(evidence.providers) > 1:
        score += 0.07
    if evidence.url and matches_post_link(post, evidence.url.unicode_string()):
        score += 0.1
    return score


def _is_candidate(post: PostData, evidence: Evidence) -> bool:
    return evaluate_source_quality(post, evidence).usable
