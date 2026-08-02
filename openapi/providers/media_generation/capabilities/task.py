from typing import Protocol

from openapi.providers.media_generation.models import (
    AudioOutput,
    AvatarOutput,
    MediaOutput,
    ModelResult,
    TaskRef,
)

TaskResult = ModelResult[MediaOutput | AvatarOutput | AudioOutput]


class TaskCapability(Protocol):
    def get_task(self, task_ref: TaskRef) -> TaskResult: ...
