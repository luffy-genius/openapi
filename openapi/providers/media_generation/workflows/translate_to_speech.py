from typing import Any, Dict, Union

from openapi.providers.media_generation.exceptions import ProviderAPIError
from openapi.providers.media_generation.models import (
    AudioOutput,
    ModelOperation,
    ModelProvider,
    ModelResult,
    TextOptimizationAction,
    TextOptimizationRequest,
    TextToSpeechRequest,
    TranslateToSpeechRequest,
)
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.validation import coerce_model


class TranslateToSpeechWorkflow:
    def __init__(self, registry: ProviderRegistry):
        self._registry = registry

    def translate_to_speech(
        self,
        request: Union[TranslateToSpeechRequest, Dict[str, Any]],
        *,
        text_provider: Union[ModelProvider, str],
        speech_provider: Union[ModelProvider, str],
    ) -> ModelResult[AudioOutput]:
        normalized = coerce_model(request, TranslateToSpeechRequest)
        speech_adapter = self._registry.speech(speech_provider)
        speech_request = TextToSpeechRequest(
            text=normalized.text,
            model=normalized.speech_model,
            voice=normalized.voice,
            language=normalized.target_language,
            title=normalized.title,
            audio_config=normalized.audio_config,
            parameters=normalized.speech_parameters,
        )
        speech_adapter.preflight_text_to_speech(speech_request)

        instruction = None
        if normalized.source_language is not None:
            instruction = f'The source language is {normalized.source_language}.'
        translation = self._registry.text(text_provider).optimize_text(
            TextOptimizationRequest(
                text=normalized.text,
                model=normalized.translation_model,
                action=TextOptimizationAction.TRANSLATE,
                target_language=normalized.target_language,
                instruction=instruction,
                parameters=normalized.translation_parameters,
            )
        )
        assert translation.output is not None
        try:
            speech = speech_adapter.text_to_speech(
                speech_request.model_copy(update={'text': translation.output.text})
            )
        except ProviderAPIError as exc:
            raise exc.with_message(
                'translation succeeded but speech generation failed; the translation request may already have '
                f'been billed: {exc}'
            ) from exc

        task_ref = speech.task_ref
        if task_ref is not None:
            task_ref = task_ref.model_copy(update={'operation': ModelOperation.TRANSLATE_TO_SPEECH})
        return ModelResult[AudioOutput](
            provider=speech.provider,
            operation=ModelOperation.TRANSLATE_TO_SPEECH,
            status=speech.status,
            model=speech.model,
            task_ref=task_ref,
            output=speech.output,
            data={'translation': translation.data, 'speech': speech.data},
            error_kind=speech.error_kind,
            error_code=speech.error_code,
            error_message=speech.error_message,
            retryable=speech.retryable,
            fallback_allowed=speech.fallback_allowed,
        )
