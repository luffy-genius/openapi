from typing import Dict, Union, cast

from openapi.enums import TextChoices
from openapi.providers.media_generation.capabilities import (
    AvatarCloneCapability,
    AvatarListCapability,
    DigitalHumanCapability,
    FileUploadCapability,
    ImageCapability,
    ImageValidationCapability,
    SpeechCapability,
    SpeechTranscriptionCapability,
    TaskCapability,
    TextCapability,
    VideoCapability,
    VoiceCloneCapability,
    VoiceDesignCapability,
    VoiceListCapability,
)
from openapi.providers.media_generation.exceptions import ConfigurationError, UnsupportedCapabilityError
from openapi.providers.media_generation.models import ModelProvider


class Capability(TextChoices):
    TEXT = 'text', '文本'
    SPEECH = 'speech', '语音'
    SPEECH_TRANSCRIPTION = 'speech transcription', '语音识别'
    VOICE_CLONE = 'voice clone', '声音复刻'
    VOICE_DESIGN = 'voice design', '音色设计'
    VOICE_LIST = 'voice list', '声音列表'
    FILE_UPLOAD = 'file upload', '文件上传'
    IMAGE = 'image', '图片'
    VIDEO = 'video', '视频'
    IMAGE_VALIDATION = 'image validation', '图片校验'
    DIGITAL_HUMAN = 'digital human', '数字人'
    AVATAR_CLONE = 'avatar clone', '形象克隆'
    AVATAR_LIST = 'avatar list', '形象列表'
    TASK = 'task query', '任务查询'


class ProviderRegistry:
    def __init__(self):
        self._providers = set()
        self._capabilities: Dict[Capability, Dict[ModelProvider, object]] = {
            capability: {} for capability in Capability
        }

    def register(self, provider: ModelProvider, adapter: object, *capabilities: Capability) -> None:
        if provider in self._providers:
            raise ConfigurationError(f'model provider {provider.value} is configured more than once')
        self._providers.add(provider)
        for capability in capabilities:
            self._capabilities[capability][provider] = adapter

    def text(self, provider: Union[ModelProvider, str]) -> TextCapability:
        return cast(TextCapability, self._get(provider, Capability.TEXT))

    def speech(self, provider: Union[ModelProvider, str]) -> SpeechCapability:
        return cast(SpeechCapability, self._get(provider, Capability.SPEECH))

    def speech_transcription(self, provider: Union[ModelProvider, str]) -> SpeechTranscriptionCapability:
        return cast(SpeechTranscriptionCapability, self._get(provider, Capability.SPEECH_TRANSCRIPTION))

    def voice_clone(self, provider: Union[ModelProvider, str]) -> VoiceCloneCapability:
        return cast(VoiceCloneCapability, self._get(provider, Capability.VOICE_CLONE))

    def voice_design(self, provider: Union[ModelProvider, str]) -> VoiceDesignCapability:
        return cast(VoiceDesignCapability, self._get(provider, Capability.VOICE_DESIGN))

    def voice_list(self, provider: Union[ModelProvider, str]) -> VoiceListCapability:
        return cast(VoiceListCapability, self._get(provider, Capability.VOICE_LIST))

    def file_upload(self, provider: Union[ModelProvider, str]) -> FileUploadCapability:
        return cast(FileUploadCapability, self._get(provider, Capability.FILE_UPLOAD))

    def image(self, provider: Union[ModelProvider, str]) -> ImageCapability:
        return cast(ImageCapability, self._get(provider, Capability.IMAGE))

    def video(self, provider: Union[ModelProvider, str]) -> VideoCapability:
        return cast(VideoCapability, self._get(provider, Capability.VIDEO))

    def image_validation(self, provider: Union[ModelProvider, str]) -> ImageValidationCapability:
        return cast(ImageValidationCapability, self._get(provider, Capability.IMAGE_VALIDATION))

    def digital_human(self, provider: Union[ModelProvider, str]) -> DigitalHumanCapability:
        return cast(DigitalHumanCapability, self._get(provider, Capability.DIGITAL_HUMAN))

    def avatar_clone(self, provider: Union[ModelProvider, str]) -> AvatarCloneCapability:
        return cast(AvatarCloneCapability, self._get(provider, Capability.AVATAR_CLONE))

    def avatar_list(self, provider: Union[ModelProvider, str]) -> AvatarListCapability:
        return cast(AvatarListCapability, self._get(provider, Capability.AVATAR_LIST))

    def task(self, provider: Union[ModelProvider, str]) -> TaskCapability:
        return cast(TaskCapability, self._get(provider, Capability.TASK))

    def _get(self, provider: Union[ModelProvider, str], capability: Capability) -> object:
        normalized = self._normalize(provider)
        if normalized not in self._providers:
            raise ConfigurationError(f'model provider {normalized.value} is not configured')
        adapter = self._capabilities[capability].get(normalized)
        if adapter is None:
            raise UnsupportedCapabilityError(f'{normalized.value} does not support {capability.value}')
        return adapter

    @staticmethod
    def _normalize(provider: Union[ModelProvider, str]) -> ModelProvider:
        try:
            return provider if isinstance(provider, ModelProvider) else ModelProvider(provider)
        except ValueError as exc:
            raise ConfigurationError(f'unknown model provider: {provider}') from exc
