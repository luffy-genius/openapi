from typing import Protocol

from openapi.providers.media_generation.models import (
    AudioOutput,
    ModelResult,
    SpeechTranscriptionRequest,
    TextOutput,
    TextToSpeechRequest,
    VoiceCloneRequest,
    VoiceDesignRequest,
    VoiceListOutput,
    VoiceOutput,
)


class SpeechCapability(Protocol):
    def preflight_text_to_speech(self, request: TextToSpeechRequest) -> None: ...

    def text_to_speech(self, request: TextToSpeechRequest) -> ModelResult[AudioOutput]: ...


class SpeechTranscriptionCapability(Protocol):
    def transcribe(self, request: SpeechTranscriptionRequest) -> ModelResult[TextOutput]: ...


class VoiceCloneCapability(Protocol):
    def clone_voice(self, request: VoiceCloneRequest) -> ModelResult[VoiceOutput]: ...


class VoiceDesignCapability(Protocol):
    def design_voice(self, request: VoiceDesignRequest) -> ModelResult[VoiceOutput]: ...


class VoiceListCapability(Protocol):
    def list_voices(self, *, page: int, size: int, kind: int = 1) -> ModelResult[VoiceListOutput]: ...
