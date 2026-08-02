from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from openapi.providers.media_generation.adapters.utils import (
    extract_chat_text,
    extract_urls,
    parse_json_object,
    require_public_url,
    secret_value,
    text_optimization_messages,
)
from openapi.providers.media_generation.exceptions import (
    ConfigurationError,
    ProviderAPIError,
    UnsupportedCapabilityError,
)
from openapi.providers.media_generation.models import (
    AudioOutput,
    DigitalHumanRequest,
    ImageGenerationRequest,
    ImageToVideoRequest,
    ImageValidationOutput,
    MediaOutput,
    ModelOperation,
    ModelProvider,
    ModelResult,
    ModelStatus,
    TaskRef,
    TextOptimizationRequest,
    TextOutput,
    TextToSpeechRequest,
    VolcengineConfig,
)
from openapi.providers.media_generation.transport import ProviderTransport


def create_visual_service():
    try:
        from volcengine.visual.VisualService import VisualService  # pyright: ignore[reportMissingImports]
    except ImportError as exc:
        raise ConfigurationError(
            "the volcengine package is required for OmniHuman; install 'openapipy[media-generation]'"
        ) from exc
    return VisualService()


class VolcengineAdapter:
    provider_name = 'volcengine'
    ark_base_url = 'https://ark.cn-beijing.volces.com/api/v3'

    def __init__(self, config: VolcengineConfig, transport: ProviderTransport):
        self.config = config
        self.transport = transport
        self._visual_service = None

    def _require_ark(self) -> str:
        key = secret_value(self.config.ark_api_key)
        if not key:
            raise ConfigurationError('volcengine ark_api_key is required for image and video generation')
        return key

    def _require_visual(self):
        ak = secret_value(self.config.access_key)
        sk = secret_value(self.config.secret_key)
        missing = [name for name, value in (('access_key', ak), ('secret_key', sk)) if not value]
        if missing:
            raise ConfigurationError(f'volcengine {", ".join(missing)} is required for OmniHuman')
        if self._visual_service is None:
            self._visual_service = create_visual_service()
        self._visual_service.set_ak(ak)
        self._visual_service.set_sk(sk)
        return self._visual_service

    def _ark_headers(self) -> Dict[str, str]:
        return {'Authorization': f'Bearer {self._require_ark()}', 'Content-Type': 'application/json'}

    def optimize_text(self, request: TextOptimizationRequest) -> ModelResult[TextOutput]:
        body = dict(request.parameters)
        body.update({'model': request.model, 'messages': text_optimization_messages(request), 'stream': False})
        payload = self.transport.request(
            'POST', f'{self.ark_base_url}/chat/completions', headers=self._ark_headers(), json_body=body
        )
        return ModelResult[TextOutput](
            provider=ModelProvider.VOLCENGINE,
            operation=ModelOperation.TEXT_OPTIMIZATION,
            status=ModelStatus.SUCCEEDED,
            model=request.model,
            output=TextOutput(text=extract_chat_text(payload, self.provider_name)),
            data=payload,
        )

    def text_to_speech(self, request: TextToSpeechRequest) -> ModelResult[AudioOutput]:
        speech = self.config.speech
        assert speech is not None
        token = secret_value(speech.access_token)
        audio = dict(request.parameters)
        audio['voice_type'] = request.voice
        config = request.audio_config
        if config.format is not None:
            audio['encoding'] = config.format
        if config.sample_rate is not None:
            audio['rate'] = config.sample_rate
        if config.speech_rate is not None:
            audio['speed_ratio'] = config.speech_rate
        if config.loudness_rate is not None:
            audio['volume_ratio'] = config.loudness_rate
        if config.pitch_rate is not None:
            audio['pitch_ratio'] = config.pitch_rate
        if config.enable_subtitle is not None:
            audio['enable_subtitle'] = config.enable_subtitle
        if request.language is not None:
            audio['language'] = request.language
        body = {
            'app': {'appid': speech.app_id, 'token': token, 'cluster': request.model},
            'user': {'uid': 'model-gateway'},
            'audio': audio,
            'request': {
                'reqid': str(uuid.uuid4()),
                'text': request.text,
                'operation': 'query',
            },
        }
        if config.watermark is not None:
            body['watermark'] = config.watermark
        payload = self.transport.request(
            'POST',
            speech.base_url,
            headers={'Authorization': f'Bearer;{token}', 'Content-Type': 'application/json'},
            json_body=body,
            capture_response_headers=True,
        )
        code = payload.get('code')
        if code not in (None, 0, 3000):
            raise ProviderAPIError(f'volcengine speech API error {code}: {payload.get("message") or "unknown error"}')
        audio_base64 = payload.get('data') or payload.get('audio')
        if not isinstance(audio_base64, str):
            audio_base64 = None
        subtitles = payload.get('subtitles')
        if not isinstance(subtitles, list):
            subtitles = []
        duration = payload.get('duration')
        duration_ms = int(duration) if isinstance(duration, (int, float)) else None
        urls = extract_urls(payload)
        if not audio_base64 and not urls:
            raise ProviderAPIError('volcengine speech response did not contain audio')
        return ModelResult[AudioOutput](
            provider=ModelProvider.VOLCENGINE,
            operation=ModelOperation.TEXT_TO_SPEECH,
            status=ModelStatus.SUCCEEDED,
            model=request.model,
            output=AudioOutput(
                urls=urls,
                audio_base64=audio_base64,
                format=config.format,
                sample_rate=config.sample_rate,
                duration_ms=duration_ms,
                subtitles=subtitles,
            ),
            data=payload,
        )

    def preflight_text_to_speech(self, request: TextToSpeechRequest) -> None:
        if self.config.speech is None:
            raise ConfigurationError('volcengine speech configuration is required for text_to_speech')

    def text_to_image(self, request: ImageGenerationRequest) -> ModelResult[MediaOutput]:
        return self._image(request, require_image=False, operation=ModelOperation.TEXT_TO_IMAGE)

    def image_to_image(self, request: ImageGenerationRequest) -> ModelResult[MediaOutput]:
        return self._image(request, require_image=True, operation=ModelOperation.IMAGE_TO_IMAGE)

    def _image(
        self, request: ImageGenerationRequest, require_image: bool, operation: ModelOperation
    ) -> ModelResult[MediaOutput]:
        if require_image and not request.images:
            raise ValueError('images must contain at least one image for image_to_image')
        body = dict(request.parameters)
        body.update({'model': request.model or self.config.image_model, 'prompt': request.prompt})
        if request.images:
            body['image'] = request.images if len(request.images) > 1 else request.images[0]
        if request.size is not None:
            body['size'] = request.size
        if request.seed is not None:
            body['seed'] = request.seed
        if request.watermark is not None:
            body['watermark'] = request.watermark
        if request.n > 1:
            body['sequential_image_generation'] = 'auto'
            body['sequential_image_generation_options'] = {'max_images': request.n}
        body.setdefault('response_format', 'url')
        payload = self.transport.request(
            'POST', f'{self.ark_base_url}/images/generations', headers=self._ark_headers(), json_body=body
        )
        model = request.model or self.config.image_model
        return ModelResult[MediaOutput](
            provider=ModelProvider.VOLCENGINE,
            operation=operation,
            status=ModelStatus.SUCCEEDED,
            model=model,
            output=MediaOutput(urls=extract_urls(payload.get('data'))),
            data=payload,
        )

    def image_to_video(self, request: ImageToVideoRequest) -> ModelResult[MediaOutput]:
        content = []
        if request.prompt:
            content.append({'type': 'text', 'text': request.prompt})
        content.append({'type': 'image_url', 'image_url': {'url': request.image}, 'role': 'first_frame'})
        if request.last_image:
            content.append({'type': 'image_url', 'image_url': {'url': request.last_image}, 'role': 'last_frame'})
        if request.audio_url:
            content.append({'type': 'audio_url', 'audio_url': {'url': request.audio_url}, 'role': 'reference_audio'})
        body = dict(request.parameters)
        body.update({'model': request.model or self.config.video_model, 'content': content})
        for key in ('duration', 'resolution', 'ratio', 'seed', 'watermark'):
            value = getattr(request, key)
            if value is not None:
                body[key] = value
        payload = self.transport.request(
            'POST', f'{self.ark_base_url}/contents/generations/tasks', headers=self._ark_headers(), json_body=body
        )
        task_id = payload.get('id') or payload.get('task_id')
        if not task_id:
            raise ProviderAPIError('volcengine video submission did not return a task id')
        ref = TaskRef(
            provider=ModelProvider.VOLCENGINE,
            operation=ModelOperation.IMAGE_TO_VIDEO,
            task_id=str(task_id),
            model=request.model or self.config.video_model,
        )
        return ModelResult[MediaOutput](
            provider=ModelProvider.VOLCENGINE,
            operation=ModelOperation.IMAGE_TO_VIDEO,
            status=ModelStatus.QUEUED,
            model=ref.model,
            task_ref=ref,
            data=payload,
        )

    def validate_digital_human_image(self, image: str) -> ModelResult[ImageValidationOutput]:
        require_public_url(image, 'image')
        payload = self._call_visual(
            'cv_process', {'req_key': 'jimeng_realman_avatar_object_detection', 'image_url': image}
        )
        self._ensure_visual_success(payload)
        provider_data = payload.get('data') or {}
        detail = parse_json_object(provider_data.get('resp_data'))
        return ModelResult[ImageValidationOutput](
            provider=ModelProvider.VOLCENGINE,
            operation=ModelOperation.DIGITAL_HUMAN_IMAGE_VALIDATION,
            status=ModelStatus.SUCCEEDED,
            output=ImageValidationOutput(passed=detail.get('status') == 1, details=detail),
            data=payload,
        )

    def digital_human(self, request: DigitalHumanRequest) -> ModelResult[MediaOutput]:
        if not request.image_url or not request.audio_url:
            raise ValueError('image_url and audio_url are required for volcengine OmniHuman')
        require_public_url(request.image_url, 'image_url')
        require_public_url(request.audio_url, 'audio_url')
        model = request.model or self.config.digital_human_model
        body = dict(request.parameters)
        body.update(
            {
                'req_key': model,
                'image_url': request.image_url,
                'audio_url': request.audio_url,
                'prompt': request.prompt,
            }
        )
        if request.seed is not None:
            body['seed'] = request.seed
        payload = self._call_visual('cv_sync2async_submit_task', body)
        self._ensure_visual_success(payload)
        task_id = (payload.get('data') or {}).get('task_id')
        if not task_id:
            raise ProviderAPIError('volcengine OmniHuman submission did not return a task id')
        ref = TaskRef(
            provider=ModelProvider.VOLCENGINE,
            operation=ModelOperation.DIGITAL_HUMAN,
            task_id=str(task_id),
            model=model,
        )
        return ModelResult[MediaOutput](
            provider=ModelProvider.VOLCENGINE,
            operation=ModelOperation.DIGITAL_HUMAN,
            status=ModelStatus.QUEUED,
            model=model,
            task_ref=ref,
            data=payload,
        )

    def get_task(self, task_ref: TaskRef) -> ModelResult[MediaOutput]:
        if task_ref.operation == ModelOperation.IMAGE_TO_VIDEO:
            payload = self.transport.request(
                'GET',
                f'{self.ark_base_url}/contents/generations/tasks/{task_ref.task_id}',
                query=True,
                headers=self._ark_headers(),
            )
            status = self._ark_status(payload.get('status'))
            urls = extract_urls(payload.get('content'))
            return ModelResult[MediaOutput](
                provider=ModelProvider.VOLCENGINE,
                operation=task_ref.operation,
                status=status,
                model=task_ref.model,
                task_ref=task_ref,
                output=MediaOutput(urls=urls) if status == ModelStatus.SUCCEEDED else None,
                data=payload,
                error_code=self._error_value(payload, 'code'),
                error_message=self._error_value(payload, 'message'),
            )
        if task_ref.operation != ModelOperation.DIGITAL_HUMAN:
            raise UnsupportedCapabilityError(
                f'volcengine does not support task operation {task_ref.operation.value}'
            )
        payload = self._call_visual(
            'cv_sync2async_get_result',
            {'req_key': task_ref.model or self.config.digital_human_model, 'task_id': task_ref.task_id},
            query=True,
        )
        self._ensure_visual_success(payload)
        data = dict(payload.get('data') or {})
        detail = parse_json_object(data.get('resp_data'))
        if detail:
            data['detail'] = detail
        status = self._visual_status(data.get('status') or detail.get('status'))
        urls = extract_urls(data)
        return ModelResult[MediaOutput](
            provider=ModelProvider.VOLCENGINE,
            operation=task_ref.operation,
            status=status,
            model=task_ref.model,
            task_ref=task_ref,
            output=MediaOutput(urls=urls) if status == ModelStatus.SUCCEEDED else None,
            data=payload,
            error_message=str(data.get('message') or '') or None,
        )

    def _call_visual(self, method: str, body: Dict[str, Any], query: bool = False) -> Dict[str, Any]:
        service = self._require_visual()
        attempts = self.transport.max_query_retries + 1 if query else 1
        payload = None
        for attempt in range(attempts):
            try:
                payload = getattr(service, method)(body)
            except Exception as exc:
                status = getattr(exc, 'status_code', None)
                is_transient = status == 429 or isinstance(status, int) and 500 <= status < 600
                if query and is_transient and attempt + 1 < attempts:
                    self.transport.sleep(0.5 * (2**attempt))
                    continue
                raise ProviderAPIError(
                    f'volcengine visual API request failed: {self.transport.redact(exc)}'
                ) from exc
            break
        assert payload is not None
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError as exc:
                raise ProviderAPIError('volcengine visual API returned invalid JSON') from exc
        if not isinstance(payload, dict):
            raise ProviderAPIError('volcengine visual API returned an invalid response object')
        return payload

    @staticmethod
    def _ensure_visual_success(payload: Dict[str, Any]):
        if payload.get('code') not in (None, 0, 10000):
            raise ProviderAPIError(
                f'volcengine visual API error {payload.get("code")}: {payload.get("message") or "unknown error"}'
            )

    @staticmethod
    def _ark_status(value: Any) -> ModelStatus:
        status = {
            'queued': ModelStatus.QUEUED,
            'running': ModelStatus.PROCESSING,
            'succeeded': ModelStatus.SUCCEEDED,
            'failed': ModelStatus.FAILED,
            'expired': ModelStatus.EXPIRED,
            'cancelled': ModelStatus.CANCELED,
            'canceled': ModelStatus.CANCELED,
        }.get(str(value).lower())
        if status is None:
            raise ProviderAPIError(f'volcengine Ark returned unknown task status: {value!r}')
        return status

    @staticmethod
    def _visual_status(value: Any) -> ModelStatus:
        status = {
            'in_queue': ModelStatus.QUEUED,
            'queued': ModelStatus.QUEUED,
            'generating': ModelStatus.PROCESSING,
            'running': ModelStatus.PROCESSING,
            'processing': ModelStatus.PROCESSING,
            'done': ModelStatus.SUCCEEDED,
            'succeeded': ModelStatus.SUCCEEDED,
            'failed': ModelStatus.FAILED,
            'expired': ModelStatus.EXPIRED,
            'not_found': ModelStatus.EXPIRED,
        }.get(str(value).lower())
        if status is None:
            raise ProviderAPIError(f'volcengine visual API returned unknown task status: {value!r}')
        return status

    @staticmethod
    def _error_value(payload: Dict[str, Any], key: str) -> Optional[str]:
        error = payload.get('error')
        value = error.get(key) if isinstance(error, dict) else None
        return str(value) if value is not None else None
