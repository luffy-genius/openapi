from typing import Any, Dict, Union

from openapi.providers.media_generation.models import (
    AudioOutput,
    ModelProvider,
    ModelResult,
    TextToSpeechRequest,
)
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.validation import coerce_model


class SpeechDomain:
    def __init__(self, registry: ProviderRegistry):
        self._registry = registry

    def synthesize(
        self,
        request: Union[TextToSpeechRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[AudioOutput]:
        normalized = coerce_model(request, TextToSpeechRequest)
        adapter = self._registry.speech(provider)
        adapter.preflight_text_to_speech(normalized)
        return adapter.text_to_speech(normalized)
