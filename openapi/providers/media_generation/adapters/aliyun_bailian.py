from __future__ import annotations

import base64
import binascii
import re
from typing import Any, Dict, Optional

from openapi.providers.media_generation.adapters.utils import (
    extract_chat_text,
    extract_urls,
    require_image_reference,
    require_public_url,
    secret_value,
    terminal_error_fields,
    text_optimization_messages,
)
from openapi.providers.media_generation.exceptions import (
    ConfigurationError,
    ProviderAPIError,
    ProviderErrorCode,
    UnsupportedCapabilityError,
    classify_provider_error,
)
from openapi.providers.media_generation.models import (
    AliyunConfig,
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
    SpeechTranscriptionRequest,
    TaskRef,
    TextOptimizationRequest,
    TextOutput,
    TextToSpeechRequest,
    VoiceCloneRequest,
    VoiceDesignRequest,
    VoiceOutput,
)
from openapi.providers.media_generation.transport import ProviderTransport


class AliyunBailianAdapter:
    provider_name = 'aliyun'
    s2v_base_url = 'https://dashscope.aliyuncs.com/api/v1'

    def __init__(self, config: AliyunConfig, transport: ProviderTransport):
        self.config = config
        self.transport = transport

    @property
    def workspace_base_url(self) -> str:
        if not self.config.workspace_id:
            raise ConfigurationError('aliyun workspace_id is required for model operations')
        return f'https://{self.config.workspace_id}.{self.config.region}.maas.aliyuncs.com'

    @property
    def base_url(self) -> str:
        return f'{self.workspace_base_url}/api/v1'

    def _headers(self, asynchronous: bool = False) -> Dict[str, str]:
        headers = {
            'Authorization': f'Bearer {secret_value(self.config.api_key)}',
            'Content-Type': 'application/json',
        }
        if asynchronous:
            headers['X-DashScope-Async'] = 'enable'
        return headers

    def optimize_text(self, request: TextOptimizationRequest) -> ModelResult[TextOutput]:
        body = dict(request.parameters)
        body.update({'model': request.model, 'messages': text_optimization_messages(request), 'stream': False})
        payload = self.transport.request(
            'POST',
            f'{self.workspace_base_url}/compatible-mode/v1/chat/completions',
            headers=self._headers(),
            json_body=body,
        )
        return ModelResult[TextOutput](
            provider=ModelProvider.ALIYUN,
            operation=ModelOperation.TEXT_OPTIMIZATION,
            status=ModelStatus.SUCCEEDED,
            model=request.model,
            output=TextOutput(text=extract_chat_text(payload, self.provider_name)),
            data=payload,
        )

    def text_to_speech(self, request: TextToSpeechRequest) -> ModelResult[AudioOutput]:
        config = request.audio_config
        input_data: Dict[str, Any] = dict(request.parameters)
        input_data.update({'text': request.text, 'voice': request.voice})
        if config.format is not None:
            input_data['format'] = config.format
        if config.sample_rate is not None:
            input_data['sample_rate'] = config.sample_rate
        if config.speech_rate is not None:
            input_data['rate'] = config.speech_rate
        if config.loudness_rate is not None:
            input_data['volume'] = round(50 * config.loudness_rate)
        if config.pitch_rate is not None:
            input_data['pitch'] = config.pitch_rate
        if request.language is not None:
            input_data['language'] = request.language
        payload = self.transport.request(
            'POST',
            f'{self.base_url}/services/audio/tts/SpeechSynthesizer',
            headers=self._headers(),
            json_body={'model': request.model, 'input': input_data},
        )
        output = payload.get('output') or {}
        audio = output.get('audio') if isinstance(output, dict) else {}
        audio = audio if isinstance(audio, dict) else {}
        urls = extract_urls(audio or output)
        audio_base64 = audio.get('data') if isinstance(audio.get('data'), str) else None
        if not audio_base64 and not urls:
            raise ProviderAPIError('aliyun speech response did not contain audio')
        return ModelResult[AudioOutput](
            provider=ModelProvider.ALIYUN,
            operation=ModelOperation.TEXT_TO_SPEECH,
            status=ModelStatus.SUCCEEDED,
            model=request.model,
            output=AudioOutput(
                urls=urls,
                audio_base64=audio_base64,
                format=config.format,
                sample_rate=config.sample_rate,
            ),
            data=payload,
        )

    def transcribe(self, request: SpeechTranscriptionRequest) -> ModelResult[TextOutput]:
        for url in request.file_urls:
            require_public_url(url, 'file_urls')
        model = request.model or self.config.asr_model
        body = {
            'model': model,
            'input': {'file_urls': request.file_urls},
            'parameters': dict(request.parameters),
        }
        payload = self.transport.request(
            'POST',
            f'{self.base_url}/services/audio/asr/transcription',
            headers=self._headers(asynchronous=True),
            json_body=body,
        )
        output = payload.get('output') if isinstance(payload.get('output'), dict) else {}
        task_id = output.get('task_id') or payload.get('task_id')
        if not task_id:
            raise ProviderAPIError('aliyun transcription submission did not return a task id')
        ref = TaskRef(
            provider=ModelProvider.ALIYUN,
            operation=ModelOperation.SPEECH_TO_TEXT,
            task_id=str(task_id),
            model=model,
        )
        return ModelResult[TextOutput](
            provider=ModelProvider.ALIYUN,
            operation=ModelOperation.SPEECH_TO_TEXT,
            status=self._status(output.get('task_status') or 'PENDING'),
            model=model,
            task_ref=ref,
            data=payload,
        )

    def clone_voice(self, request: VoiceCloneRequest) -> ModelResult[VoiceOutput]:
        if not request.audio_url:
            raise ValueError('audio_url is required for aliyun voice cloning')
        require_public_url(request.audio_url, 'audio_url')
        model = request.target_model or self.config.custom_voice_model
        input_data: Dict[str, Any] = dict(request.parameters)
        input_data.update(
            {
                'action': 'create_voice',
                'target_model': model,
                'prefix': self._safe_prefix(request.prefix),
                'url': request.audio_url,
                'max_prompt_audio_length': 30.0,
                'enable_preprocess': True,
            }
        )
        if request.language:
            input_data['language_hints'] = [request.language]
        return self._create_voice(input_data, model, ModelOperation.VOICE_CLONE)

    def design_voice(self, request: VoiceDesignRequest) -> ModelResult[VoiceOutput]:
        model = request.target_model or self.config.custom_voice_model
        input_data: Dict[str, Any] = dict(request.parameters)
        input_data.update(
            {
                'action': 'create_voice',
                'target_model': model,
                'voice_prompt': request.prompt.strip(),
                'preview_text': request.preview_text.strip(),
                'prefix': self._safe_prefix(request.prefix),
                'language_hints': [request.language],
            }
        )
        return self._create_voice(
            input_data,
            model,
            ModelOperation.VOICE_DESIGN,
            parameters={'sample_rate': request.sample_rate, 'response_format': request.response_format},
        )

    def _create_voice(
        self,
        input_data: Dict[str, Any],
        model: str,
        operation: ModelOperation,
        *,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ModelResult[VoiceOutput]:
        body: Dict[str, Any] = {'model': 'voice-enrollment', 'input': input_data}
        if parameters is not None:
            body['parameters'] = parameters
        payload = self.transport.request(
            'POST',
            f'{self.base_url}/services/audio/tts/customization',
            headers=self._headers(),
            json_body=body,
        )
        output = payload.get('output') if isinstance(payload.get('output'), dict) else {}
        voice_id = str(output.get('voice_id') or '').strip()
        if not voice_id:
            raise ProviderAPIError('aliyun voice creation did not return a voice id')
        preview = output.get('preview_audio') if isinstance(output.get('preview_audio'), dict) else {}
        preview_audio = None
        if preview:
            encoded = str(preview.get('data') or '')
            try:
                if encoded:
                    base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ProviderAPIError('aliyun voice preview contained invalid base64 audio') from exc
            preview_audio = AudioOutput(
                audio_base64=encoded or None,
                format=str(preview.get('response_format') or '') or None,
                sample_rate=parameters.get('sample_rate') if parameters else None,
            )
        request_id = str(payload.get('request_id') or '').strip() or None
        return ModelResult[VoiceOutput](
            provider=ModelProvider.ALIYUN,
            operation=operation,
            status=ModelStatus.SUCCEEDED,
            model=str(output.get('target_model') or model),
            output=VoiceOutput(
                voice_id=voice_id,
                model=str(output.get('target_model') or model),
                request_id=request_id,
                preview_audio=preview_audio,
            ),
            data=payload,
        )

    def preflight_text_to_speech(self, request: TextToSpeechRequest) -> None:
        _ = self.base_url
        if request.reference_audio is not None:
            raise UnsupportedCapabilityError('aliyun does not support reference_audio for text_to_speech')
        if not request.voice.strip():
            raise ValueError('voice is required for aliyun text_to_speech')
        config = request.audio_config
        unsupported = {
            name
            for name in ('enable_subtitle', 'watermark')
            if getattr(config, name) is not None
        }
        if unsupported:
            fields = ', '.join(sorted(unsupported))
            raise UnsupportedCapabilityError(
                f'aliyun does not support text_to_speech audio configuration fields: {fields}'
            )

    def text_to_image(self, request: ImageGenerationRequest) -> ModelResult[MediaOutput]:
        return self._image(request, require_image=False, operation=ModelOperation.TEXT_TO_IMAGE)

    def image_to_image(self, request: ImageGenerationRequest) -> ModelResult[MediaOutput]:
        return self._image(request, require_image=True, operation=ModelOperation.IMAGE_TO_IMAGE)

    def _image(
        self, request: ImageGenerationRequest, require_image: bool, operation: ModelOperation
    ) -> ModelResult[MediaOutput]:
        if require_image and not request.images:
            raise ValueError('images must contain at least one image for image_to_image')
        for image in request.images:
            require_image_reference(image, 'images')
        content = [{'image': image} for image in request.images]
        content.append({'text': request.prompt})
        parameters = dict(request.parameters)
        parameters['n'] = request.n
        for key in ('size', 'seed', 'watermark', 'negative_prompt', 'strength'):
            value = getattr(request, key)
            if value is not None:
                parameters[key] = value
        model = request.model or self.config.image_model
        body = {
            'model': model,
            'input': {'messages': [{'role': 'user', 'content': content}]},
            'parameters': parameters,
        }
        payload = self.transport.request(
            'POST',
            f'{self.base_url}/services/aigc/multimodal-generation/generation',
            headers=self._headers(),
            json_body=body,
        )
        output = payload.get('output') or payload
        task_id = output.get('task_id') if isinstance(output, dict) else None
        if task_id:
            ref = TaskRef(provider=ModelProvider.ALIYUN, operation=operation, task_id=str(task_id), model=model)
            return ModelResult[MediaOutput](
                provider=ModelProvider.ALIYUN,
                operation=operation,
                status=ModelStatus.QUEUED,
                model=model,
                task_ref=ref,
                data=payload,
            )
        return ModelResult[MediaOutput](
            provider=ModelProvider.ALIYUN,
            operation=operation,
            status=ModelStatus.SUCCEEDED,
            model=model,
            output=MediaOutput(urls=extract_urls(output)),
            data=payload,
        )

    def image_to_video(self, request: ImageToVideoRequest) -> ModelResult[MediaOutput]:
        require_image_reference(request.image, 'image')
        if request.ratio is not None and request.ratio != 'auto':
            raise UnsupportedCapabilityError(
                'aliyun Wan i2v derives ratio from the source image; only ratio="auto" is accepted'
            )
        if request.seed is not None:
            raise UnsupportedCapabilityError('aliyun Wan i2v does not support seed')
        if request.negative_prompt:
            raise UnsupportedCapabilityError('aliyun Wan i2v does not support negative_prompt')
        media = [{'type': 'first_frame', 'url': request.image}]
        if request.last_image:
            require_image_reference(request.last_image, 'last_image')
            media.append({'type': 'last_frame', 'url': request.last_image})
        if request.audio_url:
            require_public_url(request.audio_url, 'audio_url')
            media.append({'type': 'driving_audio', 'url': request.audio_url})
        parameters = dict(request.parameters)
        for key in ('duration', 'resolution', 'watermark', 'prompt_extend'):
            value = getattr(request, key)
            if value is not None:
                parameters[key] = value
        model = request.model or self.config.video_model
        body = {'model': model, 'input': {'prompt': request.prompt, 'media': media}, 'parameters': parameters}
        return self._submit_task(
            '/services/aigc/video-generation/video-synthesis',
            body,
            ModelOperation.IMAGE_TO_VIDEO,
            model,
        )

    def validate_digital_human_image(self, image: str) -> ModelResult[ImageValidationOutput]:
        self._require_beijing_digital_human()
        require_public_url(image, 'image')
        body = {'model': 'wan2.2-s2v-detect', 'input': {'image_url': image}}
        payload = self.transport.request(
            'POST',
            f'{self.s2v_base_url}/services/aigc/image2video/face-detect',
            headers=self._headers(),
            json_body=body,
        )
        output = payload.get('output')
        if not isinstance(output, dict):
            raise ProviderAPIError('aliyun image validation response did not contain an output object')
        field = 'check_pass' if 'check_pass' in output else 'passed' if 'passed' in output else None
        if field is None:
            raise ProviderAPIError('aliyun image validation response did not contain check_pass or passed')
        passed = output[field]
        if type(passed) is not bool:
            raise ProviderAPIError(f'aliyun image validation response field {field} was not a boolean')
        return ModelResult[ImageValidationOutput](
            provider=ModelProvider.ALIYUN,
            operation=ModelOperation.DIGITAL_HUMAN_IMAGE_VALIDATION,
            status=ModelStatus.SUCCEEDED,
            output=ImageValidationOutput(passed=passed, details=output),
            data=payload,
        )

    def digital_human(self, request: DigitalHumanRequest) -> ModelResult[MediaOutput]:
        self._require_beijing_digital_human()
        if not request.image_url or not request.audio_url:
            raise ValueError('image_url and audio_url are required for aliyun digital human generation')
        require_public_url(request.image_url, 'image_url')
        require_public_url(request.audio_url, 'audio_url')
        if request.resolution == '1080P':
            raise UnsupportedCapabilityError('aliyun Wan S2V supports provider output up to 720P')
        if request.ratio is not None:
            raise UnsupportedCapabilityError('aliyun Wan S2V derives ratio from the source image')
        parameters = dict(request.parameters)
        if request.resolution is not None:
            parameters['resolution'] = request.resolution
        if request.seed is not None:
            parameters['seed'] = request.seed
        model = request.model or self.config.digital_human_model
        body = {
            'model': model,
            'input': {'image_url': request.image_url, 'audio_url': request.audio_url},
            'parameters': parameters,
        }
        return self._submit_task(
            '/services/aigc/image2video/video-synthesis', body, ModelOperation.DIGITAL_HUMAN, model
        )

    def _submit_task(
        self, path: str, body: Dict[str, Any], operation: ModelOperation, model: str
    ) -> ModelResult[MediaOutput]:
        payload = self.transport.request(
            'POST', f'{self.base_url}{path}', headers=self._headers(asynchronous=True), json_body=body
        )
        output = payload.get('output') or {}
        task_id = output.get('task_id') or payload.get('task_id')
        if not task_id:
            provider_code = self._string(output.get('code') or payload.get('code'))
            provider_message = self._string(output.get('message') or payload.get('message'))
            if provider_code or provider_message:
                raise ProviderAPIError.from_provider_response(
                    f'aliyun task submission failed: {provider_message or provider_code}',
                    provider_code=provider_code,
                )
            raise ProviderAPIError(
                'aliyun task submission did not return a task id',
                code=ProviderErrorCode.INVALID_RESPONSE,
                remote_task_may_exist=True,
            )
        ref = TaskRef(provider=ModelProvider.ALIYUN, operation=operation, task_id=str(task_id), model=model)
        return ModelResult[MediaOutput](
            provider=ModelProvider.ALIYUN,
            operation=operation,
            status=self._status(output.get('task_status') or 'PENDING'),
            model=model,
            task_ref=ref,
            data=payload,
        )

    def get_task(self, task_ref: TaskRef) -> ModelResult:
        if task_ref.operation not in {
            ModelOperation.TEXT_TO_IMAGE,
            ModelOperation.IMAGE_TO_IMAGE,
            ModelOperation.IMAGE_TO_VIDEO,
            ModelOperation.DIGITAL_HUMAN,
            ModelOperation.SPEECH_TO_TEXT,
        }:
            raise UnsupportedCapabilityError(
                f'aliyun does not support task operation {task_ref.operation.value}'
            )
        payload = self.transport.request(
            'GET',
            f'{self.base_url}/tasks/{task_ref.task_id}',
            query=True,
            headers=self._headers(),
            remote_task_may_exist=True,
        )
        output = payload.get('output') or {}
        status = self._status(output.get('task_status'))
        error_code = self._string(output.get('code') or payload.get('code'))
        error_message = self._string(output.get('message') or payload.get('message'))
        error = (
            classify_provider_error(provider_code=error_code, message=error_message or '')
            if status == ModelStatus.FAILED
            else None
        )
        if status == ModelStatus.SUCCEEDED and task_ref.operation == ModelOperation.SPEECH_TO_TEXT:
            text = self._transcription_text(output)
            normalized_output = TextOutput(text=text)
        else:
            urls = extract_urls(output)
            normalized_output = MediaOutput(urls=urls) if status == ModelStatus.SUCCEEDED else None
        return ModelResult(
            provider=ModelProvider.ALIYUN,
            operation=task_ref.operation,
            status=status,
            model=task_ref.model,
            task_ref=task_ref,
            output=normalized_output,
            data=payload,
            **terminal_error_fields(error, error_code, error_message),
        )

    def _transcription_text(self, output: Dict[str, Any]) -> str:
        results = output.get('results') if isinstance(output.get('results'), list) else []
        texts = []
        for item in results:
            if not isinstance(item, dict):
                continue
            direct = str(item.get('text') or '').strip()
            if direct:
                texts.append(direct)
                continue
            url = str(item.get('transcription_url') or '').strip()
            if not url:
                continue
            transcript = self.transport.request('GET', url, query=True, remote_task_may_exist=True)
            transcripts = transcript.get('transcripts') if isinstance(transcript.get('transcripts'), list) else []
            texts.extend(
                str(part.get('text') or '').strip()
                for part in transcripts
                if isinstance(part, dict) and str(part.get('text') or '').strip()
            )
        text = '\n'.join(texts).strip()
        if not text:
            raise ProviderAPIError('aliyun transcription task succeeded without text')
        return text

    @staticmethod
    def _safe_prefix(value: str) -> str:
        return re.sub(r'[^0-9A-Za-z]+', '', value or '')[:10] or 'voice'

    @staticmethod
    def _status(value: Any) -> ModelStatus:
        status = {
            'PENDING': ModelStatus.QUEUED,
            'RUNNING': ModelStatus.PROCESSING,
            'SUCCEEDED': ModelStatus.SUCCEEDED,
            'FAILED': ModelStatus.FAILED,
            'CANCELED': ModelStatus.CANCELED,
            'CANCELLED': ModelStatus.CANCELED,
            'UNKNOWN': ModelStatus.EXPIRED,
        }.get(str(value).upper())
        if status is None:
            raise ProviderAPIError(f'aliyun API returned unknown task status: {value!r}')
        return status

    def _require_beijing_digital_human(self):
        if self.config.region != 'cn-beijing':
            raise ConfigurationError('aliyun Wan S2V digital human is only available in region cn-beijing')

    @staticmethod
    def _string(value: Any) -> Optional[str]:
        return str(value) if value is not None else None
