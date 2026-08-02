from typing import Dict, Union, cast

from openapi.enums import TextChoices
from openapi.providers.media_generation.capabilities import (
    AvatarCloneCapability,
    AvatarListCapability,
    DigitalHumanCapability,
    ImageCapability,
    ImageValidationCapability,
    SpeechCapability,
    TaskCapability,
    TextCapability,
    VideoCapability,
)
from openapi.providers.media_generation.exceptions import ConfigurationError, UnsupportedCapabilityError
from openapi.providers.media_generation.models import ModelProvider


class Capability(TextChoices):
    TEXT = 'text'
    SPEECH = 'speech'
    IMAGE = 'image'
    VIDEO = 'video'
    IMAGE_VALIDATION = 'image validation'
    DIGITAL_HUMAN = 'digital human'
    AVATAR_CLONE = 'avatar clone'
    AVATAR_LIST = 'avatar list'
    TASK = 'task query'


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
            raise UnsupportedCapabilityError(
                f'{normalized.value} does not support {capability.value}'
            )
        return adapter

    @staticmethod
    def _normalize(provider: Union[ModelProvider, str]) -> ModelProvider:
        try:
            return provider if isinstance(provider, ModelProvider) else ModelProvider(provider)
        except ValueError as exc:
            raise ConfigurationError(f'unknown model provider: {provider}') from exc
