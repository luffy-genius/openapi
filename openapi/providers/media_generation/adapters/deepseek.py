from __future__ import annotations

from typing import Dict

from openapi.providers.media_generation.adapters.utils import (
    extract_chat_text,
    secret_value,
    text_optimization_messages,
)
from openapi.providers.media_generation.models import (
    DeepSeekConfig,
    ModelOperation,
    ModelProvider,
    ModelResult,
    ModelStatus,
    TextOptimizationRequest,
    TextOutput,
)
from openapi.providers.media_generation.transport import ProviderTransport


class DeepSeekAdapter:
    provider_name = 'deepseek'

    def __init__(self, config: DeepSeekConfig, transport: ProviderTransport):
        self.config = config
        self.transport = transport

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {secret_value(self.config.api_key)}',
            'Content-Type': 'application/json',
        }

    def optimize_text(self, request: TextOptimizationRequest) -> ModelResult[TextOutput]:
        body = dict(request.parameters)
        body.update({'model': request.model, 'messages': text_optimization_messages(request), 'stream': False})
        payload = self.transport.request(
            'POST', f'{self.config.base_url}/chat/completions', headers=self._headers(), json_body=body
        )
        return ModelResult[TextOutput](
            provider=ModelProvider.DEEPSEEK,
            operation=ModelOperation.TEXT_OPTIMIZATION,
            status=ModelStatus.SUCCEEDED,
            model=request.model,
            output=TextOutput(text=extract_chat_text(payload, self.provider_name)),
            data=payload,
        )
