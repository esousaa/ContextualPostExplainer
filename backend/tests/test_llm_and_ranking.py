import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.adapters.openai.embedding_client import OpenAIEmbeddingClient
from app.adapters.openai.llm_client import OpenAILLMClient
from app.application.explanation_generator import ExplanationGenerator
from app.application.ranking import EvidenceRanker
from app.domain.models import Evidence, Explanation, ExplanationBullet, PostAuthor, PostData
from app.domain.validation import CitationValidator
from app.graphs.citation_repair import (
    repair_citation_contract_once,
    validate_citation_contract,
)

LONG_CONTEXT = (
    "Useful public context about the same event with enough extractable article text "
    "to be eligible as a citation source. The source describes the relevant actors, "
    "the timeline, the action being taken, and why it matters for public readers. "
    "This keeps the fixture above the minimum content threshold used by the live ranker."
)


class FakeResponses:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FakeEmbeddingsResource:
    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = vectors

    async def create(self, **_kwargs):
        return SimpleNamespace(data=[SimpleNamespace(embedding=vector) for vector in self._vectors])


class FakeOpenAIClient:
    def __init__(
        self,
        output_text: str | None = None,
        vectors: list[list[float]] | None = None,
    ) -> None:
        self.responses = FakeResponses(output_text or "{}")
        self.embeddings = FakeEmbeddingsResource(vectors or [])


class FakeEmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.0, 1.0],
            [0.8, 0.2],
            [0.7, 0.3],
        ]
        return vectors[: len(texts)]


class CapturingEmbeddingClient(FakeEmbeddingClient):
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.texts = texts
        return await super().embed(texts)


class RepairingLLMClient:
    async def decompose_queries(self, _post: PostData) -> list[str]:
        return ["query one", "query two"]

    async def generate_explanation(
        self,
        _post: PostData,
        _evidence: list[Evidence],
    ) -> Explanation:
        return Explanation(
            bullets=[ExplanationBullet(text="Too short.", source_ids=["missing"])],
            confidence="low",
            warnings=[],
        )

    async def repair_explanation(self, **_kwargs) -> Explanation:
        return Explanation(
            bullets=[
                ExplanationBullet(text="Supported context one.", source_ids=["s1"]),
                ExplanationBullet(text="Supported context two.", source_ids=["s1"]),
                ExplanationBullet(text="Supported context three.", source_ids=["s1"]),
            ],
            confidence="medium",
            warnings=[],
        )


class InvalidRepairLLMClient(RepairingLLMClient):
    async def repair_explanation(self, **_kwargs) -> Explanation:
        return Explanation(
            bullets=[ExplanationBullet(text="Still invalid.", source_ids=["missing"])],
            confidence="low",
            warnings=[],
        )


class SemanticRepairLLMClient(RepairingLLMClient):
    async def generate_explanation(
        self,
        _post: PostData,
        _evidence: list[Evidence],
    ) -> Explanation:
        return Explanation(
            bullets=[
                ExplanationBullet(
                    text="The post claim is externally confirmed.",
                    source_ids=["thread_original"],
                    claim_label="confirmed_fact",
                )
                for _ in range(3)
            ],
            confidence="high",
            warnings=[],
        )

    async def repair_explanation(self, **_kwargs) -> Explanation:
        return Explanation(
            bullets=[
                ExplanationBullet(
                    text="The author states the claim.",
                    source_ids=["thread_original"],
                    claim_label="author_interpretation",
                ),
                ExplanationBullet(
                    text="External context one.",
                    source_ids=["s1"],
                    claim_label="confirmed_fact",
                ),
                ExplanationBullet(
                    text="External context two.",
                    source_ids=["s1"],
                    claim_label="confirmed_fact",
                ),
            ],
            confidence="medium",
            warnings=[],
        )


class UnrepairedCriticalLLMClient(SemanticRepairLLMClient):
    async def repair_explanation(self, **_kwargs) -> Explanation:
        return await self.generate_explanation(_kwargs["post"], _kwargs["evidence"])


class OpinionRepairLLMClient(SemanticRepairLLMClient):
    async def generate_explanation(
        self,
        _post: PostData,
        _evidence: list[Evidence],
    ) -> Explanation:
        return Explanation(
            bullets=[
                ExplanationBullet(
                    text="The post says the official committed crimes.",
                    source_ids=["thread_original"],
                    claim_label="confirmed_fact",
                    warnings=["This reflects the author's opinion, not confirmed information."],
                )
                for _ in range(3)
            ],
            confidence="medium",
            warnings=[],
        )

    async def repair_explanation(self, **_kwargs) -> Explanation:
        return Explanation(
            bullets=[
                ExplanationBullet(
                    text="The author frames the official as criminal and expresses criticism.",
                    source_ids=["thread_original"],
                    claim_label="author_interpretation",
                    warnings=[
                        "This summarizes the author's framing and does not verify the accusation."
                    ],
                )
                for _ in range(3)
            ],
            confidence="medium",
            warnings=[],
        )


def _post() -> PostData:
    return PostData(
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        platform="bluesky",
        author=PostAuthor(handle="example.bsky.social"),
        text="Post about a public topic",
        created_at=datetime(2026, 5, 15, tzinfo=UTC),
    )


def _evidence(
    id_: str = "s1",
    content: str = LONG_CONTEXT,
    url: str = "https://example.com/source",
    published_at: datetime | None = None,
) -> Evidence:
    return Evidence(
        id=id_,
        title="Source",
        url=url,
        snippet="Useful snippet",
        content=content,
        source_type="web",
        published_at=published_at,
    )


def _thread_source() -> Evidence:
    return Evidence(
        id="thread_original",
        title="Original post",
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        snippet="Post",
        content="Post content",
        source_type="thread",
        source_category="social_post",
        source_role="original_post",
    )


@pytest.mark.asyncio
async def test_openai_llm_client_decomposes_queries_with_structured_output() -> None:
    fake_client = FakeOpenAIClient(output_text='{"queries":["first query","second query"]}')
    llm = OpenAILLMClient(
        api_key=SecretStr("test-openai-key"),
        generation_model="gpt-4o",
        client=fake_client,
    )

    queries = await llm.decompose_queries(_post())

    assert queries == ["first query", "second query"]
    assert fake_client.responses.calls[0]["text"]["format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_openai_llm_client_generates_explanation_schema() -> None:
    output = """
    {
      "bullets": [
        {
          "text": "One. [s1]",
          "claim_label": "confirmed_fact",
          "context_modifiers": ["background_context"],
          "source_ids": ["s1"],
          "confidence": "medium",
          "warnings": []
        },
        {
          "text": "Two.",
          "claim_label": "official_position",
          "context_modifiers": ["legal_context"],
          "source_ids": ["s1"],
          "confidence": "medium",
          "warnings": []
        },
        {
          "text": "Three.",
          "claim_label": "author_interpretation",
          "context_modifiers": ["political_context"],
          "source_ids": ["s1"],
          "confidence": "low",
          "warnings": ["Author interpretation is cited to the post context."]
        }
      ],
      "confidence": "medium",
      "warnings": []
    }
    """
    fake_client = FakeOpenAIClient(output_text=output)
    llm = OpenAILLMClient(
        api_key=SecretStr("test-openai-key"),
        generation_model="gpt-4o",
        client=fake_client,
    )

    explanation = await llm.generate_explanation(_post(), [_evidence()])

    assert len(explanation.bullets) == 3
    assert explanation.bullets[0].text == "One."
    assert explanation.bullets[0].source_ids == ["s1"]
    assert explanation.bullets[1].claim_label == "official_position"
    assert explanation.bullets[2].warnings[0].code == "GENERAL_WARNING"


@pytest.mark.asyncio
async def test_openai_llm_client_repair_instruction_prioritizes_preservation() -> None:
    output = """
    {
      "bullets": [
        {
          "text": "One.",
          "claim_label": "author_interpretation",
          "context_modifiers": ["political_context"],
          "source_ids": ["thread_original"],
          "confidence": "medium",
          "warnings": []
        },
        {
          "text": "Two.",
          "claim_label": "author_interpretation",
          "context_modifiers": ["political_context"],
          "source_ids": ["thread_original"],
          "confidence": "medium",
          "warnings": []
        },
        {
          "text": "Three.",
          "claim_label": "author_interpretation",
          "context_modifiers": ["political_context"],
          "source_ids": ["thread_original"],
          "confidence": "medium",
          "warnings": []
        }
      ],
      "confidence": "medium",
      "warnings": []
    }
    """
    fake_client = FakeOpenAIClient(output_text=output)
    llm = OpenAILLMClient(
        api_key=SecretStr("test-openai-key"),
        generation_model="gpt-4o",
        client=fake_client,
    )

    await llm.repair_explanation(
        post=_post(),
        evidence=[_thread_source()],
        invalid_payload='{"bullets":[]}',
        validation_error="SOCIAL_ONLY_CONFIRMED_FACT",
    )

    payload = json.loads(fake_client.responses.calls[0]["input"])
    assert "Preserve useful explanatory bullets" in payload["repair_instruction"]
    assert "Omit a bullet only when no compatible source" in payload["repair_instruction"]


@pytest.mark.asyncio
async def test_openai_embedding_client_returns_vectors() -> None:
    fake_client = FakeOpenAIClient(vectors=[[1.0, 0.0], [0.0, 1.0]])
    client = OpenAIEmbeddingClient(
        api_key=SecretStr("test-openai-key"),
        embedding_model="text-embedding-3-small",
        client=fake_client,
    )

    vectors = await client.embed(["one", "two"])

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]


@pytest.mark.asyncio
async def test_evidence_ranker_orders_by_similarity() -> None:
    ranker = EvidenceRanker(FakeEmbeddingClient())

    ranked = await ranker.rank(
        _post(),
        [
            _evidence("s1", f"Highly related context. {LONG_CONTEXT}"),
            _evidence("s2", f"Unrelated context. {LONG_CONTEXT}"),
        ],
    )

    assert [item.id for item in ranked] == ["s1", "s2"]
    assert ranked[0].relevance_score > ranked[1].relevance_score


@pytest.mark.asyncio
async def test_evidence_ranker_filters_low_quality_web_sources() -> None:
    ranker = EvidenceRanker(FakeEmbeddingClient())
    post = PostData(
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        platform="bluesky",
        author=PostAuthor(handle="example.bsky.social"),
        text="The DOJ sued the DC Bar over a specific current public event.",
        created_at=datetime(2026, 5, 15, tzinfo=UTC),
    )

    ranked = await ranker.rank(
        post,
        [
            _evidence(
                "fresh",
                (f"The Department of Justice sued the DC Bar in a current matter. {LONG_CONTEXT}"),
                published_at=datetime(2026, 5, 14, tzinfo=UTC),
            ),
            _evidence("short", "Too short to support a generated explanation."),
            _evidence(
                "missing-anchor",
                (
                    "This article discusses DOJ and lawyers in a historical Trump case "
                    f"without covering the specific bar action. {LONG_CONTEXT}"
                ),
                url="https://www.facebook.com/example/posts/123",
            ),
            _evidence(
                "stale",
                f"Older indictment background about DOJ and Trump. {LONG_CONTEXT}",
                published_at=datetime(2023, 8, 1, tzinfo=UTC),
            ),
        ],
    )

    assert [item.id for item in ranked] == ["fresh"]


@pytest.mark.asyncio
async def test_evidence_ranker_truncates_embedding_inputs() -> None:
    embedding_client = CapturingEmbeddingClient()
    ranker = EvidenceRanker(embedding_client)

    await ranker.rank(_post(), [_evidence(content=f"{LONG_CONTEXT} {'word ' * 20_000}")])

    assert len(embedding_client.texts) == 2
    assert all(len(text) <= 3_000 for text in embedding_client.texts)


@pytest.mark.asyncio
async def test_explanation_generator_returns_raw_generation_for_graph_validation() -> None:
    generator = ExplanationGenerator(RepairingLLMClient())

    explanation = await generator.generate(_post(), [_evidence()])

    assert len(explanation.bullets) == 1
    assert explanation.bullets[0].source_ids == ["missing"]


@pytest.mark.asyncio
async def test_citation_repair_repairs_once_after_validation_failure() -> None:
    llm_client = RepairingLLMClient()
    raw = await llm_client.generate_explanation(_post(), [_evidence()])
    validation = validate_citation_contract(raw, [_evidence()], CitationValidator())

    repaired = await repair_citation_contract_once(
        post=_post(),
        evidence=[_evidence()],
        explanation=raw,
        validation_error=validation["validation_error"],
        validation_warnings=validation["validation_warnings"],
        llm_client=llm_client,
        citation_validator=CitationValidator(),
    )

    explanation = repaired["explanation"]
    assert len(explanation.bullets) == 3
    assert explanation.confidence == "medium"
    assert repaired["citation_repair_audit"]["outcome"] == "repaired"
    assert len(repaired["citation_repair_audit"]["input_bullets"]) == 1
    assert repaired["citation_repair_audit"]["removed_bullets"] == []


@pytest.mark.asyncio
async def test_citation_repair_returns_empty_when_repair_fails() -> None:
    llm_client = InvalidRepairLLMClient()
    raw = await llm_client.generate_explanation(_post(), [_evidence()])
    validation = validate_citation_contract(raw, [_evidence()], CitationValidator())

    repaired = await repair_citation_contract_once(
        post=_post(),
        evidence=[_evidence()],
        explanation=raw,
        validation_error=validation["validation_error"],
        validation_warnings=validation["validation_warnings"],
        llm_client=llm_client,
        citation_validator=CitationValidator(),
    )

    explanation = repaired["explanation"]
    assert explanation.bullets == []
    assert explanation.confidence == "low"
    assert repaired["citation_repair_audit"]["outcome"] == "failed_validation"
    assert repaired["citation_repair_audit"]["input_bullets"][0]["source_ids"] == ["missing"]


@pytest.mark.asyncio
async def test_citation_repair_repairs_semantic_warning_once() -> None:
    llm_client = SemanticRepairLLMClient()
    evidence = [_thread_source(), _evidence()]
    raw = await llm_client.generate_explanation(_post(), evidence)
    validation = validate_citation_contract(raw, evidence, CitationValidator())

    repaired = await repair_citation_contract_once(
        post=_post(),
        evidence=evidence,
        explanation=raw,
        validation_error=validation["validation_error"],
        validation_warnings=validation["validation_warnings"],
        llm_client=llm_client,
        citation_validator=CitationValidator(),
    )

    explanation = repaired["explanation"]
    assert len(explanation.bullets) == 3
    assert explanation.confidence == "medium"
    assert {bullet.claim_label for bullet in explanation.bullets} == {
        "author_interpretation",
        "confirmed_fact",
    }
    assert explanation.warnings == []
    assert repaired["citation_repair_audit"]["outcome"] == "repaired"
    assert repaired["citation_repair_audit"]["removed_bullets"] == []


@pytest.mark.asyncio
async def test_citation_repair_preserves_opinion_bullets_by_reclassification() -> None:
    llm_client = OpinionRepairLLMClient()
    evidence = [_thread_source()]
    raw = await llm_client.generate_explanation(_post(), evidence)
    validation = validate_citation_contract(raw, evidence, CitationValidator())

    repaired = await repair_citation_contract_once(
        post=_post(),
        evidence=evidence,
        explanation=raw,
        validation_error=validation["validation_error"],
        validation_warnings=validation["validation_warnings"],
        llm_client=llm_client,
        citation_validator=CitationValidator(),
    )

    explanation = repaired["explanation"]
    assert len(explanation.bullets) == 3
    assert {bullet.claim_label for bullet in explanation.bullets} == {"author_interpretation"}
    assert repaired["citation_repair_audit"]["outcome"] == "repaired"
    assert repaired["citation_repair_audit"]["removed_bullets"] == []
    assert repaired["citation_repair_audit"]["targeted_bullet_indexes"] == [0, 1, 2]


@pytest.mark.asyncio
async def test_citation_repair_removes_unrepaired_critical_bullets() -> None:
    llm_client = UnrepairedCriticalLLMClient()
    evidence = [_thread_source(), _evidence()]
    raw = await llm_client.generate_explanation(_post(), evidence)
    validation = validate_citation_contract(raw, evidence, CitationValidator())

    repaired = await repair_citation_contract_once(
        post=_post(),
        evidence=evidence,
        explanation=raw,
        validation_error=validation["validation_error"],
        validation_warnings=validation["validation_warnings"],
        llm_client=llm_client,
        citation_validator=CitationValidator(),
    )

    explanation = repaired["explanation"]
    assert explanation.bullets == []
    assert explanation.confidence == "low"
    assert explanation.warnings[0].code == "CRITICAL_BULLETS_REMOVED"
    assert "citations did not match the claim type" in explanation.warnings[0].message
    assert (
        "confirmed factual claims were supported only by social" in explanation.warnings[0].message
    )
    assert repaired["citation_repair_audit"]["outcome"] == "hardened"
    assert len(repaired["citation_repair_audit"]["removed_bullets"]) == 3
