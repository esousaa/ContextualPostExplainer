import structlog
from openai import AsyncOpenAI, OpenAIError
from pydantic import SecretStr

from app.adapters.openai.client import build_openai_client
from app.domain.errors import ExternalProviderError
from app.observability.redaction import redact_text
from app.ports.embedding_client import EmbeddingClient

logger = structlog.get_logger(__name__)


class OpenAIEmbeddingClient(EmbeddingClient):
    def __init__(
        self,
        api_key: SecretStr,
        embedding_model: str,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._client = client or build_openai_client(api_key)
        self._embedding_model = embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            response = await self._client.embeddings.create(
                model=self._embedding_model,
                input=texts,
            )
        except OpenAIError as exc:
            logger.error("openai_embedding_failed", error=redact_text(str(exc)))
            raise ExternalProviderError("OpenAI embedding generation failed.") from exc

        vectors = [item.embedding for item in response.data]
        if len(vectors) != len(texts):
            raise ExternalProviderError("OpenAI returned an unexpected embedding count.")
        return vectors
