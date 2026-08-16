from __future__ import annotations

from typing import Any, Dict, Optional, TypeVar

from pydantic import BaseModel

from openapi.providers.media_generation.adapters.utils import (
    extract_urls,
    require_public_url,
    secret_value,
    terminal_error_fields,
)
from openapi.providers.media_generation.exceptions import (
    ProviderAPIError,
    ProviderErrorCode,
    UnsupportedCapabilityError,
    classify_provider_error,
)
from openapi.providers.media_generation.models import (
    AudioOutput,
    AvatarCloneRequest,
    AvatarListOutput,
    AvatarOutput,
    DigitalHumanRequest,
    FileUploadOutput,
    FileUploadRequest,
    HiFlyConfig,
    MediaOutput,
    ModelOperation,
    ModelProvider,
    ModelResult,
    ModelStatus,
    TaskRef,
    TextToSpeechRequest,
    VoiceCloneRequest,
    VoiceListOutput,
    VoiceOutput,
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
        if request.reference_audio is not None:
            raise UnsupportedCapabilityError('hifly does not support reference_audio for text_to_speech')
        if not request.voice.strip():
            raise ValueError('voice is required for hifly text_to_speech')
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
        if request.seed is not None:
            raise UnsupportedCapabilityError('hifly digital human does not support seed')
        if request.resolution is not None or request.ratio is not None:
            raise UnsupportedCapabilityError(
                'hifly digital human does not support resolution or ratio; '
                'output dimensions derive from the source material'
            )
        body = dict(request.parameters)
        body['avatar'] = request.avatar
        if request.title is not None:
            body['title'] = request.title
        if request.model is not None:
            body['pipeline'] = request.model
        if request.audio_url or request.file_id:
            if request.text or request.voice:
                raise ValueError('use either audio input or text and voice for hifly generation')
            if request.audio_url:
                require_public_url(request.audio_url, 'audio_url')
                body['audio_url'] = request.audio_url
            else:
                body['file_id'] = request.file_id
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
        sources = [request.image_url, request.image_file_id, request.video_url, request.video_file_id]
        if sum(bool(item) for item in sources) != 1:
            raise ValueError(
                'exactly one of image_url, image_file_id, video_url and video_file_id is required for avatar cloning'
            )
        if request.image_url or request.video_url:
            require_public_url(request.image_url or request.video_url or '', 'clone source')
        body = dict(request.parameters)
        body['title'] = request.title
        if request.aigc_flag is not None:
            body['aigc_flag'] = request.aigc_flag
        if request.image_url or request.image_file_id:
            # Per the official HiFly docs, create_by_image accepts image_url or file_id.
            if request.image_url:
                body['image_url'] = request.image_url
            else:
                body['file_id'] = request.image_file_id
            body['model'] = request.model or self.config.avatar_clone_model
            path = '/avatar/create_by_image'
        else:
            if request.video_url:
                body['video_url'] = request.video_url
            else:
                body['file_id'] = request.video_file_id
            path = '/avatar/create_by_video'
        payload = self._business_request('POST', path, json_body=body)
        model = (
            str(request.model or self.config.avatar_clone_model)
            if request.image_url or request.image_file_id
            else None
        )
        return self._queued_result(
            payload,
            operation=ModelOperation.AVATAR_CLONE,
            model=model,
            result_model=ModelResult[AvatarOutput],
            missing_task_error='hifly avatar submission did not return a task id',
        )

    def clone_voice(self, request: VoiceCloneRequest) -> ModelResult[VoiceOutput]:
        body = dict(request.parameters)
        body.update(
            {
                'title': request.title,
                'voice_type': 8,
                'languages': request.language or 'zh',
            }
        )
        if request.audio_url:
            require_public_url(request.audio_url, 'audio_url')
            body['audio_url'] = request.audio_url
        else:
            body['file_id'] = request.file_id
        payload = self._business_request('POST', '/voice/create', json_body=body)
        return self._queued_result(
            payload,
            operation=ModelOperation.VOICE_CLONE,
            model=request.target_model,
            result_model=ModelResult[VoiceOutput],
            missing_task_error='hifly voice submission did not return a task id',
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

    def list_voices(self, *, page: int, size: int, kind: int = 1) -> ModelResult[VoiceListOutput]:
        # Per the official docs: kind 1 = self-cloned voices, 2 = public voices, default 1.
        payload = self._business_request(
            'GET', '/voice/list', query=True, params={'page': page, 'size': size, 'kind': kind}
        )
        raw_items = payload.get('data')
        items = [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []
        return ModelResult[VoiceListOutput](
            provider=ModelProvider.HIFLY,
            operation=ModelOperation.VOICE_LIST,
            status=ModelStatus.SUCCEEDED,
            output=VoiceListOutput(items=items, page=page, size=size),
            data=payload,
        )

    def upload_file(self, request: FileUploadRequest) -> ModelResult[FileUploadOutput]:
        payload = self._business_request(
            'POST', '/tool/create_upload_url', json_body={'file_extension': request.file_extension}
        )
        data = self._data_object(payload)
        upload_url = str(data.get('upload_url') or '').strip()
        file_id = str(data.get('file_id') or '').strip()
        if not upload_url or not file_id:
            raise ProviderAPIError('hifly upload slot did not return upload_url and file_id')
        content_type = str(data.get('content_type') or request.content_type or 'application/octet-stream')
        self.transport.request_response(
            'PUT',
            upload_url,
            headers={'Content-Type': content_type, 'Content-Length': str(len(request.content))},
            content=request.content,
        )
        return ModelResult[FileUploadOutput](
            provider=ModelProvider.HIFLY,
            operation=ModelOperation.FILE_UPLOAD,
            status=ModelStatus.SUCCEEDED,
            output=FileUploadOutput(file_id=file_id),
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
        data = self._data_object(payload)
        task_id = data.get('task_id')
        if not task_id:
            raise ProviderAPIError(
                missing_task_error,
                code=ProviderErrorCode.INVALID_RESPONSE,
                remote_task_may_exist=True,
            )
        ref = TaskRef(provider=ModelProvider.HIFLY, operation=operation, task_id=str(task_id), model=model)
        return result_model(
            provider=ModelProvider.HIFLY,
            operation=operation,
            status=ModelStatus.QUEUED,
            model=model,
            task_ref=ref,
            data=payload,
        )

    def get_task(self, task_ref: TaskRef) -> ModelResult:
        if task_ref.operation == ModelOperation.AVATAR_CLONE:
            path = '/avatar/task'
        elif task_ref.operation == ModelOperation.VOICE_CLONE:
            path = '/voice/task'
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
        payload = self._business_request(
            'GET',
            path,
            query=True,
            params={'task_id': task_ref.task_id},
            remote_task_may_exist=True,
        )
        data = self._data_object(payload)
        status = self._status(data.get('status'))
        urls = extract_urls(data)
        error_code = self._string(data.get('code')) if data.get('code') else None
        error_message = self._string(data.get('message')) if data.get('message') else None
        error = (
            classify_provider_error(provider_code=error_code, message=error_message or '')
            if status == ModelStatus.FAILED
            else None
        )
        output = None
        if status == ModelStatus.SUCCEEDED:
            if task_ref.operation == ModelOperation.AVATAR_CLONE:
                avatar_id = data.get('avatar') or data.get('avatar_id')
                output = AvatarOutput(avatar_id=str(avatar_id) if avatar_id else None, urls=urls)
            elif task_ref.operation == ModelOperation.VOICE_CLONE:
                voice_id = data.get('voice') or data.get('voice_id')
                if not voice_id:
                    raise ProviderAPIError('hifly voice task succeeded without a voice id')
                output = VoiceOutput(voice_id=str(voice_id), model=task_ref.model)
            elif task_ref.operation in {ModelOperation.TEXT_TO_SPEECH, ModelOperation.TRANSLATE_TO_SPEECH}:
                if not urls:
                    raise ProviderAPIError('hifly speech task succeeded without an audio URL')
                output = AudioOutput(urls=urls, duration_ms=self._duration_ms(data))
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
            **terminal_error_fields(error, error_code, error_message),
        )

    def _business_request(
        self,
        method: str,
        path: str,
        *,
        query: bool = False,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        remote_task_may_exist: bool = False,
    ) -> Dict[str, Any]:
        payload = self.transport.request(
            method,
            f'{self.base_url}{path}',
            query=query,
            headers=self._headers(),
            params=params,
            json_body=json_body,
            remote_task_may_exist=remote_task_may_exist,
        )
        if payload.get('code') not in (None, 0):
            provider_code = str(payload.get('code'))
            message = self.transport.redact(payload.get('message') or 'unknown error')
            raise ProviderAPIError.from_provider_response(
                f'hifly API error {provider_code}: {message}',
                provider_code=provider_code,
                remote_task_may_exist=remote_task_may_exist,
            )
        return payload

    @staticmethod
    def _data_object(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get('data')
        return data if isinstance(data, dict) else payload

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
