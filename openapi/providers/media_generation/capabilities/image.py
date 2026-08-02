from typing import Protocol

from openapi.providers.media_generation.models import ImageGenerationRequest, MediaOutput, ModelResult


class ImageCapability(Protocol):
    def text_to_image(self, request: ImageGenerationRequest) -> ModelResult[MediaOutput]: ...

    def image_to_image(self, request: ImageGenerationRequest) -> ModelResult[MediaOutput]: ...
