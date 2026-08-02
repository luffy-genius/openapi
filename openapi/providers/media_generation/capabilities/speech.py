from typing import Protocol

from openapi.providers.media_generation.models import AudioOutput, ModelResult, TextToSpeechRequest


class SpeechCapability(Protocol):
    def preflight_text_to_speech(self, request: TextToSpeechRequest) -> None: ...

    def text_to_speech(self, request: TextToSpeechRequest) -> ModelResult[AudioOutput]: ...
