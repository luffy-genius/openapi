from __future__ import annotations

import base64
from typing import Dict, Optional

import httpx

from openapi.providers.media_generation.adapters.utils import extract_urls, secret_value
from openapi.providers.media_generation.exceptions import ProviderAPIError
from openapi.providers.media_generation.models import (
    AudioOutput,
    ModelOperation,
    ModelProvider,
    ModelResult,
    ModelStatus,
    SiliconFlowConfig,
    TextToSpeechRequest,
)
from openapi.providers.media_generation.transport import ProviderTransport
from openapi.providers.media_generation.validation import validate_siliconflow_speech_options


class SiliconFlowAdapter:
    provider_name = 'siliconflow'
    speech_path = '/audio/speech'

    def __init__(self, config: SiliconFlowConfig, transport: ProviderTransport):
        self.config = config
        self.transport = transport

    def _headers(self) -> Dict[str, str]:
        return {'Authorization': f'Bearer {secret_value(self.config.api_key)}'}

    def preflight_text_to_speech(self, request: TextToSpeechRequest) -> None:
        if request.reference_audio is not None and not (request.reference_text or '').strip():
            raise ValueError('siliconflow reference_text is required when reference_audio is provided')
        audio_config = request.audio_config
        validate_siliconflow_speech_options(
            response_format=audio_config.format or self.config.response_format,
            sample_rate=audio_config.sample_rate or self.config.sample_rate,
            speed=audio_config.speech_rate or self.config.speed,
            gain=self.config.gain,
        )

    def text_to_speech(self, request: TextToSpeechRequest) -> ModelResult[AudioOutput]:
        audio_config = request.audio_config
        body = dict(request.parameters)
        body.update(
            {
                'model': request.model,
                'input': request.text,
                'response_format': audio_config.format or self.config.response_format,
                'sample_rate': audio_config.sample_rate or self.config.sample_rate,
                'speed': audio_config.speech_rate or self.config.speed,
                'gain': self.config.gain,
                # The official parameter defaults to true (SSE); this adapter only parses
                # binary/JSON responses, so streaming is explicitly disabled.
                'stream': False,
            }
        )
        if request.reference_audio is not None:
            # Per-request dynamic references; the official contract accepts either an audio URL
            # or a `data:audio/<type>;base64,...` string for references[].audio.
            normalized_type = (request.reference_content_type or '').split(';', 1)[0].strip().lower()
            if not normalized_type.startswith('audio/'):
                normalized_type = 'audio/mpeg'
            encoded = base64.b64encode(request.reference_audio).decode('ascii')
            body['references'] = [
                {'audio': f'data:{normalized_type};base64,{encoded}', 'text': request.reference_text or ''}
            ]
        else:
            voice = request.voice or self.config.default_voice
            if not voice:
                raise ProviderAPIError('siliconflow voice is not configured')
            body['voice'] = voice
        response = self.transport.request_response(
            'POST',
            f'{self.config.base_url}{self.speech_path}',
            headers=self._headers(),
            json_body=body,
        )
        content, content_type, urls = self._audio_response(response)
        return ModelResult[AudioOutput](
            provider=ModelProvider.SILICONFLOW,
            operation=ModelOperation.TEXT_TO_SPEECH,
            status=ModelStatus.SUCCEEDED,
            model=request.model,
            output=AudioOutput(
                urls=urls,
                audio_base64=base64.b64encode(content).decode('ascii') if content else None,
                format=self._audio_format(content_type, str(body['response_format'])),
                sample_rate=int(body['sample_rate']),
            ),
        )

    def _audio_response(self, response: httpx.Response) -> tuple[bytes, str, list[str]]:
        content_type = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
        if self._is_audio(response.content, content_type):
            return response.content, content_type or 'audio/mpeg', []
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderAPIError('siliconflow speech response did not contain valid audio') from exc
        urls = extract_urls(payload)
        if not urls:
            raise ProviderAPIError('siliconflow speech response did not contain audio or an audio URL')
        download = self.transport.request_response('GET', urls[0], follow_redirects=True)
        download_type = download.headers.get('content-type', '').split(';', 1)[0].strip().lower()
        if not self._is_audio(download.content, download_type):
            raise ProviderAPIError('siliconflow audio URL did not return valid audio')
        return download.content, download_type or 'audio/mpeg', urls

    @staticmethod
    def _is_audio(content: bytes, content_type: str) -> bool:
        return content_type.startswith('audio/') or content.startswith(
            (b'ID3', b'RIFF', b'OggS', b'fLaC', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2')
        )

    @staticmethod
    def _audio_format(content_type: str, fallback: str) -> Optional[str]:
        if content_type.startswith('audio/'):
            return content_type.split('/', 1)[1]
        return fallback or None
