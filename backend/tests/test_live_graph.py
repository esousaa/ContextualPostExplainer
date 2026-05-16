import pytest
from pydantic import SecretStr

from app.application.image_evidence_builder import (
    build_image_evidence,
    image_context_text,
)
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


class PartiallyFailingSearchProvider(FakeSearchProvider):
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if "source" in query:
            raise RuntimeError("search provider timeout")
        return await super().search(query, max_results=max_results)


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
            providers=result.providers or [result.provider],
            provider_queries=result.provider_queries,
            provider_result_count=result.provider_result_count,
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


class RepairingLLMClient(FakeLLMClient):
    def __init__(self) -> None:
        self.repair_calls = 0

    async def generate_explanation(
        self,
        _post: PostData,
        _evidence: list[Evidence],
    ) -> Explanation:
        return Explanation(
            bullets=[ExplanationBullet(text="Invalid citation.", source_ids=["missing"])],
            confidence="low",
            warnings=[],
        )

    async def repair_explanation(self, **_kwargs) -> Explanation:
        self.repair_calls += 1
        return Explanation(
            bullets=[
                ExplanationBullet(text="Repaired context one.", source_ids=["s1"]),
                ExplanationBullet(text="Repaired context two.", source_ids=["s1"]),
                ExplanationBullet(text="Repaired context three.", source_ids=["s1"]),
            ],
            confidence="medium",
            warnings=[],
        )


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


class CapturingRunRecorder:
    def __init__(self) -> None:
        self.events = []
        self.runs = []
        self.write_event_counts = []

    async def record_event(self, event):
        self.events.append(event)

    async def write_run(self, mode: str, run_id: str, payload: dict) -> None:
        self.write_event_counts.append(len(self.events))
        self.runs.append((mode, run_id, payload))


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
        comparison_group_id="test_group",
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
async def test_live_explanation_flow_keeps_partial_search_results_when_one_query_fails() -> None:
    async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
        return [
            RankedEvidence(**source.model_dump(mode="json"), relevance_score=0.9)
            for source in state.get("evidence", [])
            if source.id == "s1"
        ]

    async def generate_explanation(state: ExplanationState) -> Explanation:
        return await FakeLLMClient().generate_explanation(
            state["post"],
            state.get("ranked_evidence", []),
        )

    recorder = CapturingRunRecorder()
    flow = LiveExplanationFlow(
        settings=_settings(),
        post_fetcher=FakePostFetcher(),
        search_provider=PartiallyFailingSearchProvider([_search_result()]),
        source_fetcher=FakeSourceFetcher(),
        llm_client=FakeLLMClient(),
        rank_evidence=rank_evidence,
        generate_explanation=generate_explanation,
        run_recorder=recorder,
    )

    response = await flow.run("https://bsky.app/profile/example.bsky.social/post/abc")

    assert len(response.explanation) == 3
    assert recorder.runs[0][2]["metrics"]["search_errors"] == [
        {"query": "public topic source", "error": "search provider timeout"}
    ]


@pytest.mark.asyncio
async def test_live_explanation_flow_repairs_citations_in_repair_node() -> None:
    llm_client = RepairingLLMClient()
    recorder = CapturingRunRecorder()

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
        post_fetcher=FakePostFetcher(),
        search_provider=FakeSearchProvider([_search_result()]),
        source_fetcher=FakeSourceFetcher(),
        llm_client=llm_client,
        rank_evidence=rank_evidence,
        generate_explanation=generate_explanation,
        run_recorder=recorder,
    )

    response = await flow.run("https://bsky.app/profile/example.bsky.social/post/abc")

    assert llm_client.repair_calls == 1
    assert len(response.explanation) == 3
    assert response.confidence == "medium"
    audit = recorder.runs[0][2]["citation_repair_audit"]
    assert audit["outcome"] == "repaired"
    assert audit["input_bullets"][0]["source_ids"] == ["missing"]
    assert audit["removed_bullets"] == []


@pytest.mark.asyncio
async def test_live_explanation_flow_emits_progress_events() -> None:
    events = []

    async def progress_callback(event):
        events.append(event)

    async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
        return [
            RankedEvidence(**source.model_dump(mode="json"), relevance_score=0.9)
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
        progress_callback=progress_callback,
    )

    await flow.run("https://bsky.app/profile/example.bsky.social/post/abc")

    assert events[0]["type"] == "run_started"
    assert any(event["type"] == "node_started" for event in events)
    assert any(
        event["type"] == "node_completed"
        and event["node_name"] == "fetch_source_pages"
        and event["step"] == "Reading sources"
        for event in events
    )
    assert events[-1]["status"] == "completed"


@pytest.mark.asyncio
async def test_live_explanation_flow_records_completed_run_after_final_node_completion() -> None:
    recorder = CapturingRunRecorder()

    async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
        return [
            RankedEvidence(**source.model_dump(mode="json"), relevance_score=0.9)
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
        run_recorder=recorder,
    )

    await flow.run("https://bsky.app/profile/example.bsky.social/post/abc")

    assert recorder.runs[0][2]["status"] == "completed"
    assert recorder.runs[0][2]["search_provider"] == "brave"
    assert recorder.runs[0][2]["openai_generation_model"] == "gpt-4o"
    assert recorder.runs[0][2]["comparison_group_id"] == "test_group"
    assert recorder.runs[0][2]["comparison_config_id"]
    assert recorder.runs[0][2]["prompt_config_hash"]
    assert recorder.write_event_counts[0] == len(recorder.events)
    assert recorder.events[-1]["event"] == "node_completed"
    assert recorder.events[-1]["node_name"] == "finalize_response"


@pytest.mark.asyncio
async def test_live_explanation_flow_adds_image_analysis_before_query_planning() -> None:
    class ImagePostFetcher(FakePostFetcher):
        async def fetch(self, url: str) -> PostData:
            post = await super().fetch(url)
            return post.model_copy(
                update={
                    "text": "",
                    "images": [
                        ImageContext(url="https://cdn.bsky.app/img/feed_fullsize/plain/image.jpeg")
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


@pytest.mark.asyncio
async def test_live_explanation_flow_records_failed_runs() -> None:
    class FailingPostFetcher(FakePostFetcher):
        async def fetch(self, _url: str) -> PostData:
            raise RuntimeError("post fetch failed")

    async def rank_evidence(_state: ExplanationState) -> list[RankedEvidence]:
        return []

    async def generate_explanation(_state: ExplanationState) -> Explanation:
        raise AssertionError("generate should not be called")

    recorder = CapturingRunRecorder()
    flow = LiveExplanationFlow(
        settings=_settings(),
        post_fetcher=FailingPostFetcher(),
        search_provider=FakeSearchProvider([_search_result()]),
        source_fetcher=FakeSourceFetcher(),
        llm_client=FakeLLMClient(),
        rank_evidence=rank_evidence,
        generate_explanation=generate_explanation,
        run_recorder=recorder,
    )

    with pytest.raises(RuntimeError):
        await flow.run("https://bsky.app/profile/example.bsky.social/post/abc")

    assert recorder.runs[0][0] == "live"
    assert recorder.runs[0][2]["status"] == "failed"
    assert recorder.runs[0][2]["error"]["message"] == "post fetch failed"
