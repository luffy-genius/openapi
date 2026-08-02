from typing import Any, Dict, Union

from openapi.providers.media_generation.models import (
    ImageToVideoRequest,
    MediaOutput,
    ModelProvider,
    ModelResult,
)
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.validation import coerce_model


class VideoDomain:
    def __init__(self, registry: ProviderRegistry):
        self._registry = registry

    def from_image(
        self,
        request: Union[ImageToVideoRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[MediaOutput]:
        normalized = coerce_model(request, ImageToVideoRequest)
        return self._registry.video(provider).image_to_video(normalized)
