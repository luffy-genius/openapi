from typing import Protocol

from openapi.providers.media_generation.models import ImageToVideoRequest, MediaOutput, ModelResult


class VideoCapability(Protocol):
    def image_to_video(self, request: ImageToVideoRequest) -> ModelResult[MediaOutput]: ...
