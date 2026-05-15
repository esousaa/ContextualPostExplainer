from app.application.source_classification import classify_evidence
from app.domain.models import Evidence, PostData


def build_image_evidence(post: PostData) -> list[Evidence]:
    sources: list[Evidence] = []
    for index, image in enumerate(post.images, start=1):
        content = _image_content(
            image.alt_text,
            image.ocr_text,
            image.description,
            image.image_type,
        )
        if not content:
            continue
        sources.append(
            classify_evidence(
                Evidence(
                    id=f"image_{index}",
                    title=f"Image {index} from Bluesky post by @{post.author.handle}",
                    url=image.url or post.url,
                    snippet=content[:300],
                    content=content,
                    source_type="image",
                    provider="bluesky",
                    publisher=post.author.handle,
                )
            )
        )
    return sources


def image_context_text(post: PostData) -> str:
    parts: list[str] = []
    for image in post.images:
        parts.extend(
            part
            for part in [image.alt_text, image.ocr_text, image.description]
            if part
        )
    return "\n\n".join(parts)


def _image_content(
    alt_text: str | None,
    ocr_text: str | None,
    description: str | None,
    image_type: str | None,
) -> str:
    parts = []
    if image_type:
        parts.append(f"Image type: {image_type}")
    if alt_text:
        parts.append(f"Alt text: {alt_text}")
    if ocr_text:
        parts.append(f"Visible text: {ocr_text}")
    if description:
        parts.append(f"Visual description: {description}")
    return "\n".join(parts)
