from typing import Any, Dict, Union

from openapi.providers.media_generation.models import (
    AudioOutput,
    ModelProvider,
    ModelResult,
    SpeechTranscriptionRequest,
    TextOutput,
    TextToSpeechRequest,
    VoiceCloneRequest,
    VoiceDesignRequest,
    VoiceListOutput,
    VoiceOutput,
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

    def transcribe(
        self,
        request: Union[SpeechTranscriptionRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[TextOutput]:
        normalized = coerce_model(request, SpeechTranscriptionRequest)
        return self._registry.speech_transcription(provider).transcribe(normalized)

    def clone_voice(
        self,
        request: Union[VoiceCloneRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[VoiceOutput]:
        normalized = coerce_model(request, VoiceCloneRequest)
        return self._registry.voice_clone(provider).clone_voice(normalized)

    def design_voice(
        self,
        request: Union[VoiceDesignRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[VoiceOutput]:
        normalized = coerce_model(request, VoiceDesignRequest)
        return self._registry.voice_design(provider).design_voice(normalized)

    def list_voices(
        self,
        *,
        provider: Union[ModelProvider, str],
        page: int = 1,
        size: int = 20,
        kind: int = 1,
    ) -> ModelResult[VoiceListOutput]:
        from openapi.providers.media_generation.validation import require_positive_integer

        require_positive_integer(page, 'page')
        require_positive_integer(size, 'size')
        require_positive_integer(kind, 'kind')
        return self._registry.voice_list(provider).list_voices(page=page, size=size, kind=kind)
