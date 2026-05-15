from collections.abc import Awaitable, Callable
from typing import Any

from app.adapters.bluesky.post_fetcher import BlueskyPostFetcher
from app.adapters.http.source_fetcher import HttpSourceFetcher
from app.adapters.openai.embedding_client import OpenAIEmbeddingClient
from app.adapters.openai.image_analyzer import OpenAIImageAnalyzer
from app.adapters.openai.llm_client import OpenAILLMClient
from app.adapters.search.registry import get_live_search_provider
from app.application.explanation_generator import ExplanationGenerator
from app.application.ranking import EvidenceRanker
from app.config import Settings
from app.domain.models import Explanation, ExplanationResponse, RankedEvidence
from app.graphs.live_graph import LiveExplanationFlow
from app.graphs.state import ExplanationState
from app.observability.run_recorder import LocalRunRecorder


class LiveExplanationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def explain_url(
        self,
        url: str,
        include_debug: bool = False,
        progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> ExplanationResponse:
        flow = self._build_flow(progress_callback=progress_callback)
        return await flow.run(url=url, include_debug=include_debug)

    def _build_flow(
        self,
        progress_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> LiveExplanationFlow:
        llm_client = OpenAILLMClient(
            api_key=self._settings.openai_api_key,
            generation_model=self._settings.openai_generation_model,
        )
        embedding_client = OpenAIEmbeddingClient(
            api_key=self._settings.openai_api_key,
            embedding_model=self._settings.openai_embedding_model,
        )
        ranker = EvidenceRanker(embedding_client)
        generator = ExplanationGenerator(llm_client)
        image_analyzer = (
            OpenAIImageAnalyzer(
                api_key=self._settings.openai_api_key,
                vision_model=self._settings.openai_vision_model,
            )
            if self._settings.openai_vision_model
            else None
        )

        async def rank_evidence(state: ExplanationState) -> list[RankedEvidence]:
            return await ranker.rank(state["post"], state.get("evidence", []), top_n=8)

        async def generate_explanation(state: ExplanationState) -> Explanation:
            return await generator.generate(state["post"], state.get("ranked_evidence", []))

        return LiveExplanationFlow(
            settings=self._settings,
            post_fetcher=BlueskyPostFetcher(),
            search_provider=get_live_search_provider(self._settings),
            source_fetcher=HttpSourceFetcher(),
            llm_client=llm_client,
            rank_evidence=rank_evidence,
            generate_explanation=generate_explanation,
            image_analyzer=image_analyzer,
            run_recorder=LocalRunRecorder(),
            progress_callback=progress_callback,
        )
