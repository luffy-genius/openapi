from typing import Protocol

from openapi.providers.media_generation.models import (
    AvatarCloneRequest,
    AvatarListOutput,
    AvatarOutput,
    DigitalHumanRequest,
    FileUploadOutput,
    FileUploadRequest,
    ImageValidationOutput,
    MediaOutput,
    ModelResult,
)


class ImageValidationCapability(Protocol):
    def validate_digital_human_image(self, image: str) -> ModelResult[ImageValidationOutput]: ...


class DigitalHumanCapability(Protocol):
    def digital_human(self, request: DigitalHumanRequest) -> ModelResult[MediaOutput]: ...


class AvatarCloneCapability(Protocol):
    def create_avatar(self, request: AvatarCloneRequest) -> ModelResult[AvatarOutput]: ...


class AvatarListCapability(Protocol):
    def list_avatars(self, *, page: int, size: int) -> ModelResult[AvatarListOutput]: ...


class FileUploadCapability(Protocol):
    def upload_file(self, request: FileUploadRequest) -> ModelResult[FileUploadOutput]: ...
