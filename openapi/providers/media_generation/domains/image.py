from typing import Any, Dict, Union

from openapi.providers.media_generation.models import (
    ImageGenerationRequest,
    MediaOutput,
    ModelProvider,
    ModelResult,
)
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.validation import coerce_model


class ImageDomain:
    def __init__(self, registry: ProviderRegistry):
        self._registry = registry

    def generate(
        self,
        request: Union[ImageGenerationRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[MediaOutput]:
        normalized = coerce_model(request, ImageGenerationRequest)
        return self._registry.image(provider).text_to_image(normalized)

    def edit(
        self,
        request: Union[ImageGenerationRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[MediaOutput]:
        normalized = coerce_model(request, ImageGenerationRequest)
        return self._registry.image(provider).image_to_image(normalized)
