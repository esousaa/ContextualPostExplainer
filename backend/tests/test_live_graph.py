import pytest
from pydantic import SecretStr

from app.application.image_context import build_image_evidence, image_context_text
from app.config import Settings
from app.domain.models import (
    Evidence,
    Explanation,
    ExplanationBullet,
    ImageContext,
    PostAuthor,
    PostData,
    RankedEvidence,
    SearchResult,
)
from app.graphs.live_graph import LiveExplanationFlow, _thread_evidence_sources
from app.graphs.state import ExplanationState


class FakePostFetcher:
    def can_handle(self, _url: str) -> bool:
        return True

    async def fetch(self, url: str) -> PostData:
        return PostData(
            url=url,
            platform="bluesky",
            author=PostAuthor(handle="example.bsky.social"),
            text="Post about a public topic.",
            thread_text="A reply adds context.",
        )


class FakeSearchProvider:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return [result.model_copy(update={"query": query}) for result in self.results[:max_results]]


class FakeSourceFetcher:
    async def fetch(self, result: SearchResult) -> Evidence:
        return Evidence(
            id="s1",
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            content="Reliable source content that supports three explanatory bullets.",
            source_type="web",
            provider=result.provider,
            query=result.query,
            canonical_url=result.canonical_url,
        )


class FakeLLMClient:
    async def decompose_queries(self, _post: PostData) -> list[str]:
        return ["public topic context", "public topic source"]

    async def generate_explanation(
        self,
        _post: PostData,
        _evidence: list[Evidence],
    ) -> Explanation:
        return Explanation(
            bullets=[
                ExplanationBullet(text="Context one.", source_ids=["s1"]),
                ExplanationBullet(text="Context two.", source_ids=["s1"]),
                ExplanationBullet(text="Context three.", source_ids=["s1"]),
            ],
            confidence="medium",
            warnings=[],
        )

    async def repair_explanation(self, **_kwargs) -> Explanation:
        raise AssertionError("repair should not be called")


class FakeImageAnalyzer:
    async def analyze(self, post: PostData) -> PostData:
        images = [
            image.model_copy(
                update={
                    "ocr_text": "Visible claim in the image",
                    "description": "A screenshot with a public announcement.",
                    "image_type": "screenshot",
                }
            )
            for image in post.images
        ]
        return post.model_copy(update={"images": images})


def _settings() -> Settings:
    return Settings(
        openai_api_key=SecretStr("test-openai-key"),
        openai_generation_model="gpt-4o",
        openai_judge_model="gpt-4o-mini",
        openai_embedding_model="text-embedding-3-small",
        backend_cors_origins=["http://localhost:5173"],
        eval_fixture_dir="eval/fixtures",
        search_provider="brave",
        brave_api_key=SecretStr("test-brave-key"),
    )


def _search_result() -> SearchResult:
    return SearchResult(
        provider="brave",
        query="original",
        title="Source",
        url="https://example.com/source",
        snippet="Useful snippet",
        rank=1,
    )


def test_thread_evidence_sources_separate_original_post_from_context() -> None:
    post = PostData(
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        platform="bluesky",
        author=PostAuthor(handle="example.bsky.social"),
        text="Original post text.",
        thread_text="A reply adds third-party context.",
    )

    sources = _thread_evidence_sources(post)

    assert sources[0].id == "thread_original"
    assert sources[0].content == "Original post text."
    assert sources[0].source_role == "original_post"
    assert sources[1].id == "thread_context"
    assert sources[1].content == "A reply adds third-party context."
    assert sources[1].source_role == "public_reaction"


def test_image_context_builds_citable_image_evidence() -> None:
    post = PostData(
        url="https://bsky.app/profile/example.bsky.social/post/abc",
        platform="bluesky",
        author=PostAuthor(handle="example.bsky.social"),
        text="",
        images=[
            ImageContext(
                url="https://cdn.bsky.app/img/feed_fullsize/plain/image.jpeg",
                alt_text="Alt text from Bluesky.",
                ocr_text="Visible text from image.",
                description="A photo with readable text.",
                image_type="photo",
            )
        ],
    )

    evidence = build_image_evidence(post)

    assert image_context_text(post)
    assert evidence[0].id == "image_1"
    assert evidence[0].source_type == "image"
    assert evidence[0].source_role == "image_observation"
    assert "Visible text from image." in evidence[0].content


@pytest.mark.asyncio
async def test_live_explanation_flow_runs_end_to_end_with_fakes() -> None:
    async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
        return [
            RankedEvidence(
                **source.model_dump(mode="json"),
                relevance_score=0.9,
            )
            for source in state.get("evidence", [])
            if source.id == "s1"
        ]

    async def generate_explanation(state: ExplanationState) -> Explanation:
        return await FakeLLMClient().generate_explanation(
            state["post"],
            state.get("ranked_evidence", []),
        )

    flow = LiveExplanationFlow(
        settings=_settings(),
        post_fetcher=FakePostFetcher(),
        search_provider=FakeSearchProvider([_search_result()]),
        source_fetcher=FakeSourceFetcher(),
        llm_client=FakeLLMClient(),
        rank_evidence=rank_evidence,
        generate_explanation=generate_explanation,
    )

    response = await flow.run("https://bsky.app/profile/example.bsky.social/post/abc")

    assert len(response.explanation) == 3
    assert response.sources[0].id == "s1"
    assert response.confidence == "medium"


@pytest.mark.asyncio
async def test_live_explanation_flow_adds_image_analysis_before_query_planning() -> None:
    class ImagePostFetcher(FakePostFetcher):
        async def fetch(self, url: str) -> PostData:
            post = await super().fetch(url)
            return post.model_copy(
                update={
                    "text": "",
                    "images": [
                        ImageContext(
                            url="https://cdn.bsky.app/img/feed_fullsize/plain/image.jpeg"
                        )
                    ],
                }
            )

    class CapturingLLMClient(FakeLLMClient):
        def __init__(self) -> None:
            self.seen_post: PostData | None = None

        async def decompose_queries(self, post: PostData) -> list[str]:
            self.seen_post = post
            return await super().decompose_queries(post)

    llm_client = CapturingLLMClient()

    async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
        return [
            RankedEvidence(**source.model_dump(mode="json"), relevance_score=0.9)
            for source in state.get("evidence", [])
            if source.id == "s1"
        ]

    async def generate_explanation(state: ExplanationState) -> Explanation:
        return await llm_client.generate_explanation(
            state["post"],
            state.get("ranked_evidence", []),
        )

    flow = LiveExplanationFlow(
        settings=_settings(),
        post_fetcher=ImagePostFetcher(),
        search_provider=FakeSearchProvider([_search_result()]),
        source_fetcher=FakeSourceFetcher(),
        llm_client=llm_client,
        rank_evidence=rank_evidence,
        generate_explanation=generate_explanation,
        image_analyzer=FakeImageAnalyzer(),
    )

    response = await flow.run("https://bsky.app/profile/example.bsky.social/post/abc")

    assert response.explanation
    assert llm_client.seen_post is not None
    assert llm_client.seen_post.images[0].ocr_text == "Visible claim in the image"


@pytest.mark.asyncio
async def test_live_explanation_flow_returns_empty_when_search_has_no_sources() -> None:
    async def rank_evidence(_state: ExplanationState) -> list[RankedEvidence]:
        return []

    async def generate_explanation(_state: ExplanationState) -> Explanation:
        return Explanation(
            bullets=[],
            confidence="low",
            warnings=["Insufficient evidence to generate a reliable explanation."],
        )

    flow = LiveExplanationFlow(
        settings=_settings(),
        post_fetcher=FakePostFetcher(),
        search_provider=FakeSearchProvider([]),
        source_fetcher=FakeSourceFetcher(),
        llm_client=FakeLLMClient(),
        rank_evidence=rank_evidence,
        generate_explanation=generate_explanation,
    )

    response = await flow.run("https://bsky.app/profile/example.bsky.social/post/abc")

    assert response.explanation == []
    assert response.sources == []
    assert response.confidence == "low"
