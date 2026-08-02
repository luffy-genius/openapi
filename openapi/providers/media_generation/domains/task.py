from __future__ import annotations

import time
from typing import Any, Callable, Dict, Union

from openapi.providers.media_generation.capabilities import TaskResult
from openapi.providers.media_generation.exceptions import GenerationTimeoutError
from openapi.providers.media_generation.models import TaskRef
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.validation import coerce_model


class TaskDomain:
    def __init__(self, registry: ProviderRegistry, sleep: Callable[[float], None] = time.sleep):
        self._registry = registry
        self._sleep = sleep

    def get(self, task_ref: Union[TaskRef, Dict[str, Any]]) -> TaskResult:
        ref = coerce_model(task_ref, TaskRef)
        return self._registry.task(ref.provider).get_task(ref)

    def wait(
        self,
        task_ref: Union[TaskRef, Dict[str, Any]],
        *,
        timeout: float = 1800,
        poll_interval: float = 5,
    ) -> TaskResult:
        if timeout < 0:
            raise ValueError('timeout must be greater than or equal to zero')
        if poll_interval <= 0:
            raise ValueError('poll_interval must be greater than zero')
        ref = coerce_model(task_ref, TaskRef)
        deadline = time.monotonic() + timeout
        while True:
            result = self.get(ref)
            if result.done:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise GenerationTimeoutError(
                    f'timed out waiting for {ref.provider.value} {ref.operation.value} task {ref.task_id}; '
                    'the remote task was not cancelled'
                )
            self._sleep(min(poll_interval, remaining))
