from __future__ import annotations

import json
from typing import Any, Dict, Optional

from pydantic import SecretStr

from openapi.providers.media_generation.exceptions import ProviderAPIError, ProviderErrorClassification
from openapi.providers.media_generation.models import TextOptimizationAction, TextOptimizationRequest


def secret_value(value: Optional[SecretStr]) -> Optional[str]:
    return value.get_secret_value() if value is not None else None


def terminal_error_fields(
    error: Optional[ProviderErrorClassification],
    error_code: Optional[str],
    error_message: Optional[str],
) -> Dict[str, Any]:
    """Assemble the terminal-state error fields shared by all task adapters."""
    return {
        'error_kind': error.code if error else None,
        'error_code': error_code,
        'error_message': error_message,
        'retryable': error.retryable if error else False,
        'fallback_allowed': error.fallback_allowed if error else False,
    }


def require_public_url(value: str, field: str) -> None:
    if not value.startswith(('http://', 'https://')):
        raise ValueError(f'{field} must be a public HTTP/HTTPS URL')


def require_image_reference(value: str, field: str) -> None:
    if not value.startswith(('http://', 'https://', 'data:image/')):
        raise ValueError(f'{field} must be a public HTTP/HTTPS URL or image data URI')


def extract_urls(value: Any) -> list:
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {
                'url',
                'image',
                'image_url',
                'video_url',
                'video_Url',
                'audio_url',
                'audio_Url',
                'demo_url',
            } and isinstance(item, str):
                if item.startswith(('http://', 'https://', 'data:')):
                    found.append(item)
            else:
                found.extend(extract_urls(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(extract_urls(item))
    return list(dict.fromkeys(found))


def parse_json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def text_optimization_messages(request: TextOptimizationRequest) -> list[Dict[str, str]]:
    system = (
        'You rewrite text according to the requested operation. Preserve the original meaning and all factual '
        'claims. Do not invent facts. Return only the rewritten body without commentary, labels, or Markdown fences.'
    )
    action = {
        TextOptimizationAction.POLISH: 'Polish the text for clarity, fluency, and natural expression.',
        TextOptimizationAction.EXPAND: 'Expand the text with useful detail while preserving its meaning and facts.',
        TextOptimizationAction.SIMPLIFY: 'Simplify the text while retaining its essential meaning and facts.',
        TextOptimizationAction.TRANSLATE: f'Translate the text into {request.target_language}.',
    }[request.action]
    requirements = [action]
    if request.style is not None:
        requirements.append(f'Use a {request.style.value} style.')
    if request.instruction is not None:
        requirements.append(f'Additional requirements: {request.instruction}')
    requirements.append(f'Text:\n{request.text}')
    return [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': '\n\n'.join(requirements)},
    ]


def extract_chat_text(payload: Dict[str, Any], provider_name: str) -> str:
    choices = payload.get('choices')
    message = (
        choices[0].get('message') if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    )
    content = message.get('content') if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ProviderAPIError(f'{provider_name} text optimization response did not contain rewritten text')
    return content
