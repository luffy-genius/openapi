from __future__ import annotations

from typing import Callable, Optional, Union

import httpx

from openapi.providers.media_generation.domains import (
    AvatarDomain,
    ImageDomain,
    SpeechDomain,
    TaskDomain,
    TextDomain,
    VideoDomain,
)
from openapi.providers.media_generation.models import (
    AliyunConfig,
    DeepSeekConfig,
    HiFlyConfig,
    VolcengineConfig,
)
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.workflows import TranslateToSpeechWorkflow

ProviderConfig = Union[AliyunConfig, DeepSeekConfig, HiFlyConfig, VolcengineConfig]


class MediaClient:
    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        http_client: httpx.Client,
        owns_http_client: bool,
        task_sleep: Optional[Callable[[float], None]] = None,
    ):
        self.text = TextDomain(registry)
        self.speech = SpeechDomain(registry)
        self.image = ImageDomain(registry)
        self.video = VideoDomain(registry)
        self.avatar = AvatarDomain(registry)
        self.task = TaskDomain(registry, sleep=task_sleep) if task_sleep is not None else TaskDomain(registry)
        self.workflow = TranslateToSpeechWorkflow(registry)
        self._http_client = http_client
        self._owns_http_client = owns_http_client

    @classmethod
    def create(
        cls,
        *configs: ProviderConfig,
        http_client: Optional[httpx.Client] = None,
        sleep: Optional[Callable[[float], None]] = None,
    ) -> MediaClient:
        from openapi.providers.media_generation.factory import create_media_client

        return create_media_client(
            *configs,
            http_client=http_client,
            sleep=sleep,
        )

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> MediaClient:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
