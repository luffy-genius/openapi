from typing import Any, Dict, Union

from openapi.providers.media_generation.models import (
    ModelProvider,
    ModelResult,
    TextOptimizationRequest,
    TextOutput,
)
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.validation import coerce_model


class TextDomain:
    def __init__(self, registry: ProviderRegistry):
        self._registry = registry

    def optimize(
        self,
        request: Union[TextOptimizationRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[TextOutput]:
        normalized = coerce_model(request, TextOptimizationRequest)
        return self._registry.text(provider).optimize_text(normalized)
