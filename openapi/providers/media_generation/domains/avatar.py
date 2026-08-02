from typing import Any, Dict, Union

from openapi.providers.media_generation.models import (
    AvatarCloneRequest,
    AvatarListOutput,
    AvatarOutput,
    DigitalHumanRequest,
    ImageValidationOutput,
    MediaOutput,
    ModelProvider,
    ModelResult,
)
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.validation import coerce_model, require_positive_integer


class AvatarDomain:
    def __init__(self, registry: ProviderRegistry):
        self._registry = registry

    def validate_image(
        self, image: str, *, provider: Union[ModelProvider, str]
    ) -> ModelResult[ImageValidationOutput]:
        return self._registry.image_validation(provider).validate_digital_human_image(image)

    def render(
        self,
        request: Union[DigitalHumanRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[MediaOutput]:
        normalized = coerce_model(request, DigitalHumanRequest)
        return self._registry.digital_human(provider).digital_human(normalized)

    def clone(
        self,
        request: Union[AvatarCloneRequest, Dict[str, Any]],
        *,
        provider: Union[ModelProvider, str],
    ) -> ModelResult[AvatarOutput]:
        normalized = coerce_model(request, AvatarCloneRequest)
        return self._registry.avatar_clone(provider).create_avatar(normalized)

    def list(
        self,
        *,
        provider: Union[ModelProvider, str],
        page: int = 1,
        size: int = 20,
    ) -> ModelResult[AvatarListOutput]:
        require_positive_integer(page, 'page')
        require_positive_integer(size, 'size')
        return self._registry.avatar_list(provider).list_avatars(page=page, size=size)
