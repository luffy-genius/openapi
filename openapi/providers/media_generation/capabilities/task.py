from typing import Protocol

from openapi.providers.media_generation.models import (
    AudioOutput,
    AvatarOutput,
    MediaOutput,
    ModelResult,
    TaskRef,
    TextOutput,
    VoiceOutput,
)

TaskResult = ModelResult[MediaOutput | AvatarOutput | AudioOutput | TextOutput | VoiceOutput]


class TaskCapability(Protocol):
    def get_task(self, task_ref: TaskRef) -> TaskResult: ...
