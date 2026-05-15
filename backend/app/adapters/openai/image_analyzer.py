import json

import structlog
from openai import AsyncOpenAI, OpenAIError
from pydantic import SecretStr, ValidationError

from app.adapters.openai.client import build_openai_client
from app.adapters.openai.prompt_loader import load_prompt
from app.adapters.openai.schemas import ImageAnalysisOutput
from app.domain.errors import ExternalProviderError
from app.domain.models import ImageContext, PostData
from app.observability.redaction import redact_text
from app.ports.image_analyzer import ImageAnalyzer

logger = structlog.get_logger(__name__)


class OpenAIImageAnalyzer(ImageAnalyzer):
    def __init__(
        self,
        api_key: SecretStr,
        vision_model: str,
        client: AsyncOpenAI | None = None,
    ) -> None:
        self._client = client or build_openai_client(api_key)
        self._vision_model = vision_model

    async def analyze(self, post: PostData) -> PostData:
        analyzed_images: list[ImageContext] = []
        for image in post.images:
            if image.url is None:
                analyzed_images.append(image)
                continue
            analyzed_images.append(await self._analyze_image(post, image))
        return post.model_copy(update={"images": analyzed_images})

    async def _analyze_image(self, post: PostData, image: ImageContext) -> ImageContext:
        payload = {
            "post_text": post.text,
            "author": post.author.model_dump(mode="json"),
            "alt_text": image.alt_text,
            "image_url": image.url.unicode_string() if image.url else None,
        }
        try:
            response = await self._client.responses.create(
                model=self._vision_model,
                instructions=load_prompt("image_analysis"),
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": json.dumps(payload, ensure_ascii=False),
                            },
                            {
                                "type": "input_image",
                                "image_url": image.url.unicode_string(),
                            },
                        ],
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "image_analysis",
                        "schema": ImageAnalysisOutput.model_json_schema(),
                        "strict": True,
                    }
                },
                max_output_tokens=900,
            )
        except OpenAIError as exc:
            logger.error("image_analysis_failed", error=redact_text(str(exc)))
            raise ExternalProviderError("OpenAI image analysis failed.") from exc

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise ExternalProviderError("OpenAI returned an empty image analysis.")

        try:
            parsed = ImageAnalysisOutput.model_validate_json(output_text)
        except ValidationError as exc:
            logger.error("image_analysis_schema_failed", error=redact_text(str(exc)))
            raise ExternalProviderError("OpenAI returned invalid image analysis output.") from exc

        return image.model_copy(
            update={
                "ocr_text": _clean_optional_text(parsed.ocr_text),
                "description": _clean_optional_text(parsed.description),
                "image_type": _clean_optional_text(parsed.image_type),
            }
        )


def _clean_optional_text(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None
