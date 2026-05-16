from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from app.adapters.openai.groundedness_judge import (
    GROUNDEDNESS_MAX_OUTPUT_TOKENS,
    OpenAIGroundednessJudge,
)
from app.domain.errors import ExternalProviderError
from app.domain.models import Evidence, ExplanationBullet


class SequenceResponses:
    def __init__(self, outputs: list[str]) -> None:
        self._outputs = outputs
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self._outputs) - 1)
        return SimpleNamespace(output_text=self._outputs[index])


class SequenceOpenAIClient:
    def __init__(self, outputs: list[str]) -> None:
        self.responses = SequenceResponses(outputs)


@pytest.mark.asyncio
async def test_groundedness_judge_retries_invalid_json_once() -> None:
    client = SequenceOpenAIClient(
        [
            '{"verdict":"partially_supported","reason":"truncated',
            '{"verdict":"supported","reason":"The cited source directly supports the bullet."}',
        ]
    )
    judge = OpenAIGroundednessJudge(
        api_key=SecretStr("test-openai-key"),
        judge_model="gpt-4o-mini",
        client=client,  # type: ignore[arg-type]
    )

    assessment = await judge.judge(
        0,
        ExplanationBullet(text="The source supports this claim.", source_ids=["s1"]),
        [
            Evidence(
                id="s1",
                title="Source",
                snippet="Snippet",
                content="The source supports this claim with direct evidence.",
                source_type="fixture",
            )
        ],
    )

    assert assessment.verdict == "supported"
    assert len(client.responses.calls) == 2
    assert client.responses.calls[0]["max_output_tokens"] == GROUNDEDNESS_MAX_OUTPUT_TOKENS


@pytest.mark.asyncio
async def test_groundedness_judge_fails_after_invalid_retries() -> None:
    client = SequenceOpenAIClient(["not-json", "still-not-json"])
    judge = OpenAIGroundednessJudge(
        api_key=SecretStr("test-openai-key"),
        judge_model="gpt-4o-mini",
        client=client,  # type: ignore[arg-type]
    )

    with pytest.raises(ExternalProviderError):
        await judge.judge(
            0,
            ExplanationBullet(text="The source supports this claim.", source_ids=["s1"]),
            [
                Evidence(
                    id="s1",
                    title="Source",
                    snippet="Snippet",
                    content="The source supports this claim with direct evidence.",
                    source_type="fixture",
                )
            ],
        )

    assert len(client.responses.calls) == 2
