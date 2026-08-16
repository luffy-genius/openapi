from __future__ import annotations

import time
from typing import Callable, Optional

import httpx

from openapi.providers.media_generation.adapters import (
    AliyunBailianAdapter,
    DeepSeekAdapter,
    HiFlyAdapter,
    SiliconFlowAdapter,
    VolcengineAdapter,
)
from openapi.providers.media_generation.adapters.utils import secret_value
from openapi.providers.media_generation.client import MediaClient, ProviderConfig
from openapi.providers.media_generation.exceptions import ConfigurationError
from openapi.providers.media_generation.models import (
    AliyunConfig,
    DeepSeekConfig,
    HiFlyConfig,
    ModelProvider,
    SiliconFlowConfig,
    VolcengineConfig,
)
from openapi.providers.media_generation.registry import Capability, ProviderRegistry
from openapi.providers.media_generation.transport import ProviderTransport


def create_media_client(
    *configs: ProviderConfig,
    http_client: Optional[httpx.Client] = None,
    sleep: Optional[Callable[[float], None]] = None,
    timeout: float = 300.0,
) -> MediaClient:
    providers = [_provider_for_config(config) for config in configs]
    duplicate = next((provider for provider in providers if providers.count(provider) > 1), None)
    if duplicate is not None:
        raise ConfigurationError(f'model provider {duplicate.value} is configured more than once')

    if timeout <= 0:
        raise ValueError('timeout must be greater than zero')
    client = http_client or httpx.Client(timeout=httpx.Timeout(timeout))
    registry = ProviderRegistry()
    request_sleep = sleep if sleep is not None else time.sleep

    for config in configs:
        if isinstance(config, AliyunConfig):
            provider = ModelProvider.ALIYUN
            transport = ProviderTransport(
                client,
                provider_name=provider.value,
                secrets=(secret_value(config.api_key) or '',),
                sleep=request_sleep,
            )
            adapter = AliyunBailianAdapter(config, transport)
            registry.register(
                provider,
                adapter,
                Capability.TEXT,
                Capability.SPEECH,
                Capability.SPEECH_TRANSCRIPTION,
                Capability.VOICE_CLONE,
                Capability.VOICE_DESIGN,
                Capability.IMAGE,
                Capability.VIDEO,
                Capability.IMAGE_VALIDATION,
                Capability.DIGITAL_HUMAN,
                Capability.TASK,
            )
        elif isinstance(config, VolcengineConfig):
            provider = ModelProvider.VOLCENGINE
            secrets = (
                secret_value(config.ark_api_key) or '',
                secret_value(config.access_key) or '',
                secret_value(config.secret_key) or '',
                (secret_value(config.speech.access_token) or '') if config.speech is not None else '',
            )
            transport = ProviderTransport(
                client,
                provider_name=provider.value,
                secrets=secrets,
                sleep=request_sleep,
            )
            adapter = VolcengineAdapter(config, transport)
            registry.register(
                provider,
                adapter,
                Capability.TEXT,
                Capability.SPEECH,
                Capability.IMAGE,
                Capability.VIDEO,
                Capability.IMAGE_VALIDATION,
                Capability.DIGITAL_HUMAN,
                Capability.TASK,
            )
        elif isinstance(config, HiFlyConfig):
            provider = ModelProvider.HIFLY
            transport = ProviderTransport(
                client,
                provider_name=provider.value,
                secrets=(secret_value(config.token) or '',),
                sleep=request_sleep,
            )
            adapter = HiFlyAdapter(config, transport)
            registry.register(
                provider,
                adapter,
                Capability.SPEECH,
                Capability.DIGITAL_HUMAN,
                Capability.AVATAR_CLONE,
                Capability.AVATAR_LIST,
                Capability.VOICE_CLONE,
                Capability.VOICE_LIST,
                Capability.FILE_UPLOAD,
                Capability.TASK,
            )
        elif isinstance(config, DeepSeekConfig):
            provider = ModelProvider.DEEPSEEK
            transport = ProviderTransport(
                client,
                provider_name=provider.value,
                secrets=(secret_value(config.api_key) or '',),
                sleep=request_sleep,
            )
            adapter = DeepSeekAdapter(config, transport)
            registry.register(provider, adapter, Capability.TEXT)
        elif isinstance(config, SiliconFlowConfig):
            provider = ModelProvider.SILICONFLOW
            transport = ProviderTransport(
                client,
                provider_name=provider.value,
                secrets=(secret_value(config.api_key) or '',),
                sleep=request_sleep,
            )
            adapter = SiliconFlowAdapter(config, transport)
            registry.register(provider, adapter, Capability.SPEECH)
        else:
            raise ConfigurationError(f'unsupported provider config type: {type(config).__name__}')

    return MediaClient(
        registry,
        http_client=client,
        owns_http_client=http_client is None,
        task_sleep=sleep,
    )


def _provider_for_config(config: ProviderConfig) -> ModelProvider:
    if isinstance(config, AliyunConfig):
        return ModelProvider.ALIYUN
    if isinstance(config, VolcengineConfig):
        return ModelProvider.VOLCENGINE
    if isinstance(config, HiFlyConfig):
        return ModelProvider.HIFLY
    if isinstance(config, DeepSeekConfig):
        return ModelProvider.DEEPSEEK
    if isinstance(config, SiliconFlowConfig):
        return ModelProvider.SILICONFLOW
    raise ConfigurationError(f'unsupported provider config type: {type(config).__name__}')
