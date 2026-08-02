from __future__ import annotations

from typing import Any, Dict, Optional, TypeVar

from pydantic import BaseModel

from openapi.providers.media_generation.adapters.utils import extract_urls, require_public_url, secret_value
from openapi.providers.media_generation.exceptions import ProviderAPIError, UnsupportedCapabilityError
from openapi.providers.media_generation.models import (
    AudioOutput,
    AvatarCloneRequest,
    AvatarListOutput,
    AvatarOutput,
    DigitalHumanRequest,
    HiFlyConfig,
    MediaOutput,
    ModelOperation,
    ModelProvider,
    ModelResult,
    ModelStatus,
    TaskRef,
    TextToSpeechRequest,
)
from openapi.providers.media_generation.transport import ProviderTransport

QueuedOutputT = TypeVar('QueuedOutputT', bound=BaseModel)


class HiFlyAdapter:
    provider_name = 'hifly'
    base_url = 'https://hfw-api.hifly.cc/api/v2/hifly'

    def __init__(self, config: HiFlyConfig, transport: ProviderTransport):
        self.config = config
        self.transport = transport

    def _headers(self) -> Dict[str, str]:
        return {
            'Authorization': f'Bearer {secret_value(self.config.token)}',
            'Content-Type': 'application/json',
        }

    def text_to_speech(self, request: TextToSpeechRequest) -> ModelResult[AudioOutput]:
        config = request.audio_config
        body = dict(request.parameters)
        body.update({'voice': request.voice, 'text': request.text, 'title': request.title or '未命名'})
        if config.watermark is not None:
            body['aigc_flag'] = config.watermark['aigc_flag']
        payload = self._business_request('POST', '/audio/create_by_tts', json_body=body)
        return self._queued_result(
            payload,
            operation=ModelOperation.TEXT_TO_SPEECH,
            model=request.model,
            result_model=ModelResult[AudioOutput],
            missing_task_error='hifly audio submission did not return a task id',
        )

    def preflight_text_to_speech(self, request: TextToSpeechRequest) -> None:
        config = request.audio_config
        unsupported = {
            name
            for name in (
                'format',
                'sample_rate',
                'speech_rate',
                'loudness_rate',
                'pitch_rate',
                'enable_subtitle',
            )
            if getattr(config, name) is not None
        }
        if unsupported:
            fields = ', '.join(sorted(unsupported))
            raise UnsupportedCapabilityError(
                f'hifly does not support text_to_speech configuration fields: {fields}'
            )
        if config.watermark is not None:
            aigc_flag = config.watermark.get('aigc_flag')
            if aigc_flag is None:
                raise ValueError('hifly watermark must contain aigc_flag')

    def digital_human(self, request: DigitalHumanRequest) -> ModelResult[MediaOutput]:
        if not request.avatar:
            raise ValueError('avatar is required for hifly digital human generation')
        body = dict(request.parameters)
        body['avatar'] = request.avatar
        if request.title is not None:
            body['title'] = request.title
        if request.model is not None:
            body['pipeline'] = request.model
        if request.audio_url:
            require_public_url(request.audio_url, 'audio_url')
            if request.text or request.voice:
                raise ValueError('use either audio_url or text and voice for hifly generation')
            body['audio_url'] = request.audio_url
            path = '/video/create_by_audio'
        else:
            if not request.text or not request.voice:
                raise ValueError('audio_url or both text and voice are required for hifly generation')
            body.update({'text': request.text, 'voice': request.voice})
            path = '/video/create_by_tts'
        payload = self._business_request('POST', path, json_body=body)
        return self._queued_result(
            payload,
            operation=ModelOperation.DIGITAL_HUMAN,
            model=request.model,
            result_model=ModelResult[MediaOutput],
            missing_task_error='hifly video submission did not return a task id',
        )

    def create_avatar(self, request: AvatarCloneRequest) -> ModelResult[AvatarOutput]:
        if bool(request.image_url) == bool(request.video_url):
            raise ValueError('exactly one of image_url and video_url is required for avatar cloning')
        source = request.image_url or request.video_url
        assert source is not None
        require_public_url(source, 'clone source')
        body = dict(request.parameters)
        body['title'] = request.title
        if request.aigc_flag is not None:
            body['aigc_flag'] = request.aigc_flag
        if request.image_url:
            body.update({'image_url': request.image_url, 'model': request.model or self.config.avatar_clone_model})
            path = '/avatar/create_by_image'
        else:
            body['video_url'] = request.video_url
            path = '/avatar/create_by_video'
        payload = self._business_request('POST', path, json_body=body)
        model = str(request.model or self.config.avatar_clone_model) if request.image_url else None
        return self._queued_result(
            payload,
            operation=ModelOperation.AVATAR_CLONE,
            model=model,
            result_model=ModelResult[AvatarOutput],
            missing_task_error='hifly avatar submission did not return a task id',
        )

    def list_avatars(self, *, page: int, size: int) -> ModelResult[AvatarListOutput]:
        payload = self._business_request(
            'GET', '/avatar/list', query=True, params={'page': page, 'size': size, 'kind': 2}
        )
        raw_items = payload.get('data')
        items = [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []
        return ModelResult[AvatarListOutput](
            provider=ModelProvider.HIFLY,
            operation=ModelOperation.AVATAR_LIST,
            status=ModelStatus.SUCCEEDED,
            output=AvatarListOutput(items=items, page=page, size=size),
            data=payload,
        )

    def _queued_result(
        self,
        payload: Dict[str, Any],
        *,
        operation: ModelOperation,
        model: Optional[str],
        result_model: type[ModelResult[QueuedOutputT]],
        missing_task_error: str,
    ) -> ModelResult[QueuedOutputT]:
        task_id = payload.get('task_id')
        if not task_id:
            raise ProviderAPIError(missing_task_error)
        ref = TaskRef(provider=ModelProvider.HIFLY, operation=operation, task_id=str(task_id), model=model)
        return result_model(
            provider=ModelProvider.HIFLY,
            operation=operation,
            status=ModelStatus.QUEUED,
            model=model,
            task_ref=ref,
            data=payload,
        )

    def get_task(self, task_ref: TaskRef) -> ModelResult[MediaOutput | AvatarOutput | AudioOutput]:
        if task_ref.operation == ModelOperation.AVATAR_CLONE:
            path = '/avatar/task'
        elif task_ref.operation in {
            ModelOperation.DIGITAL_HUMAN,
            ModelOperation.TEXT_TO_SPEECH,
            ModelOperation.TRANSLATE_TO_SPEECH,
        }:
            path = '/video/task'
        else:
            raise UnsupportedCapabilityError(
                f'hifly does not support task operation {task_ref.operation.value}'
            )
        payload = self._business_request('GET', path, query=True, params={'task_id': task_ref.task_id})
        status = self._status(payload.get('status'))
        urls = extract_urls(payload)
        output = None
        if status == ModelStatus.SUCCEEDED:
            if task_ref.operation == ModelOperation.AVATAR_CLONE:
                avatar_id = payload.get('avatar') or payload.get('avatar_id')
                output = AvatarOutput(avatar_id=str(avatar_id) if avatar_id else None, urls=urls)
            elif task_ref.operation in {ModelOperation.TEXT_TO_SPEECH, ModelOperation.TRANSLATE_TO_SPEECH}:
                if not urls:
                    raise ProviderAPIError('hifly speech task succeeded without an audio URL')
                output = AudioOutput(urls=urls, duration_ms=self._duration_ms(payload))
            else:
                output = MediaOutput(urls=urls)
        return ModelResult(
            provider=ModelProvider.HIFLY,
            operation=task_ref.operation,
            status=status,
            model=task_ref.model,
            task_ref=task_ref,
            output=output,
            data=payload,
            error_code=self._string(payload.get('code')) if payload.get('code') else None,
            error_message=self._string(payload.get('message')) if payload.get('message') else None,
        )

    def _business_request(
        self,
        method: str,
        path: str,
        *,
        query: bool = False,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = self.transport.request(
            method,
            f'{self.base_url}{path}',
            query=query,
            headers=self._headers(),
            params=params,
            json_body=json_body,
        )
        if payload.get('code') not in (None, 0):
            raise ProviderAPIError(
                f'hifly API error {payload.get("code")}: '
                f'{self.transport.redact(payload.get("message") or "unknown error")}'
            )
        return payload

    @staticmethod
    def _status(value: Any) -> ModelStatus:
        status = {
            1: ModelStatus.QUEUED,
            2: ModelStatus.PROCESSING,
            3: ModelStatus.SUCCEEDED,
            4: ModelStatus.FAILED,
        }.get(value)
        if status is None:
            raise ProviderAPIError(f'hifly API returned unknown task status: {value!r}')
        return status

    @staticmethod
    def _duration_ms(payload: Dict[str, Any]) -> Optional[int]:
        duration = payload.get('duration')
        return int(float(duration) * 1000) if duration is not None else None

    @staticmethod
    def _string(value: Any) -> Optional[str]:
        return str(value) if value is not None else None
