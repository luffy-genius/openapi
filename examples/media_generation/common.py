from __future__ import annotations

import base64
import binascii
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from openapi.providers.media_generation import (
    AliyunConfig,
    AudioOutput,
    AvatarListOutput,
    AvatarOutput,
    DeepSeekConfig,
    GenerationTimeoutError,
    HiFlyConfig,
    ImageValidationOutput,
    MediaClient,
    MediaOutput,
    ModelProvider,
    ModelResult,
    ModelStatus,
    SiliconFlowConfig,
    TaskRef,
    TextOutput,
    VolcengineConfig,
    VolcengineSpeechConfig,
)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / 'output'


class ExampleError(Exception):
    """An expected, safely reportable example error."""


def env_string(name: str, *, required: bool = False, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(name)
    if value is None or not value.strip():
        if required:
            raise ExampleError(f'missing required environment variable: {name}')
        return default
    return value.strip()


def env_integer(
    name: str,
    *,
    required: bool = False,
    default: Optional[int] = None,
    minimum: Optional[int] = None,
) -> Optional[int]:
    value = env_string(name, required=required)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ExampleError(f'{name} must be an integer') from exc
    if minimum is not None and parsed < minimum:
        raise ExampleError(f'{name} must be greater than or equal to {minimum}')
    return parsed


def optional_values(**values):
    return {name: value for name, value in values.items() if value is not None}


def provider_config(provider: ModelProvider, capability: str):
    if provider == ModelProvider.DEEPSEEK:
        return DeepSeekConfig(
            api_key=env_string('MEDIA_DEEPSEEK_API_KEY', required=True),
            **optional_values(base_url=env_string('MEDIA_DEEPSEEK_BASE_URL')),
        )
    if provider == ModelProvider.ALIYUN:
        workspace_required = capability not in {'image_validation'}
        return AliyunConfig(
            api_key=env_string('MEDIA_ALIYUN_API_KEY', required=True),
            **optional_values(
                workspace_id=env_string('MEDIA_ALIYUN_WORKSPACE_ID', required=workspace_required),
                region=env_string('MEDIA_ALIYUN_REGION'),
            ),
        )
    if provider == ModelProvider.HIFLY:
        return HiFlyConfig(
            token=env_string('MEDIA_HIFLY_TOKEN', required=True),
            **optional_values(
                avatar_clone_model=env_integer('MEDIA_HIFLY_AVATAR_CLONE_MODEL', minimum=1)
                if capability == 'avatar_clone'
                else None
            ),
        )
    if provider == ModelProvider.VOLCENGINE:
        values: Dict[str, Any] = {}
        if capability in {'text', 'image', 'video'}:
            values['ark_api_key'] = env_string('MEDIA_VOLCENGINE_ARK_API_KEY', required=True)
        elif capability == 'speech':
            values['speech'] = VolcengineSpeechConfig(
                app_id=env_string('MEDIA_VOLCENGINE_SPEECH_APP_ID', required=True),
                access_token=env_string('MEDIA_VOLCENGINE_SPEECH_ACCESS_TOKEN', required=True),
                **optional_values(base_url=env_string('MEDIA_VOLCENGINE_SPEECH_BASE_URL')),
            )
        elif capability in {'image_validation', 'digital_human'}:
            values['access_key'] = env_string('MEDIA_VOLCENGINE_ACCESS_KEY', required=True)
            values['secret_key'] = env_string('MEDIA_VOLCENGINE_SECRET_KEY', required=True)
        else:
            raise ExampleError(f'unsupported volcengine capability: {capability}')
        return VolcengineConfig(**values)
    if provider == ModelProvider.SILICONFLOW:
        return SiliconFlowConfig(
            api_key=env_string('MEDIA_SILICONFLOW_API_KEY', required=True),
            **optional_values(
                base_url=env_string('MEDIA_SILICONFLOW_BASE_URL'),
                default_voice=env_string('MEDIA_SILICONFLOW_VOICE'),
            ),
        )
    raise ExampleError(f'unsupported provider: {provider.value}')


@contextmanager
def media_client(provider: ModelProvider, capability: str) -> Iterator[MediaClient]:
    media = MediaClient.create(provider_config(provider, capability))
    try:
        yield media
    finally:
        media.close()


@contextmanager
def workflow_client(speech_provider: ModelProvider) -> Iterator[MediaClient]:
    media = MediaClient.create(
        provider_config(ModelProvider.DEEPSEEK, 'text'),
        provider_config(speech_provider, 'speech'),
    )
    try:
        yield media
    finally:
        media.close()


def output_dir() -> Path:
    configured = env_string('MEDIA_OUTPUT_DIR')
    path = Path(configured).expanduser() if configured else DEFAULT_OUTPUT_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_task_ref(task_ref: TaskRef) -> Path:
    safe_id = re.sub(r'[^A-Za-z0-9_.-]+', '_', task_ref.task_id)
    path = output_dir() / f'{task_ref.provider.value}-{task_ref.operation.value}-{safe_id}.json'
    path.write_text(task_ref.to_json() + '\n', encoding='utf-8')
    print(f'task_ref: {path}')
    return path


def load_task_ref() -> TaskRef:
    value = env_string('MEDIA_TASK_REF', required=True)
    assert value is not None
    if value.lstrip().startswith('{'):
        payload = value
    else:
        path = Path(value).expanduser()
        try:
            payload = path.read_text(encoding='utf-8')
        except OSError as exc:
            raise ExampleError(f'unable to read MEDIA_TASK_REF file: {path}') from exc
    try:
        return TaskRef.from_json(payload)
    except ValueError as exc:
        raise ExampleError('MEDIA_TASK_REF must be a TaskRef JSON value or a path to one') from exc


def capability_for_task(task_ref: TaskRef) -> str:
    if task_ref.provider == ModelProvider.VOLCENGINE:
        if task_ref.operation.value == 'image_to_video':
            return 'video'
        if task_ref.operation.value == 'digital_human':
            return 'digital_human'
        raise ExampleError(f'volcengine cannot resume operation: {task_ref.operation.value}')
    if task_ref.provider == ModelProvider.ALIYUN:
        return 'task'
    if task_ref.provider == ModelProvider.HIFLY:
        return 'avatar_clone' if task_ref.operation.value == 'avatar_clone' else 'digital_human'
    raise ExampleError(f'{task_ref.provider.value} does not support resumable tasks')


def complete_result(media: MediaClient, result: ModelResult[Any]) -> ModelResult[Any]:
    _print_status(result)
    task_path = None
    if result.task_ref is not None:
        task_path = save_task_ref(result.task_ref)
    if not result.done:
        if result.task_ref is None:
            raise ExampleError('provider returned a pending result without a TaskRef')
        try:
            result = media.task.wait(
                result.task_ref,
                timeout=env_integer('MEDIA_TASK_TIMEOUT', default=1800, minimum=0),
                poll_interval=env_integer('MEDIA_POLL_INTERVAL', default=5, minimum=1),
            )
        except GenerationTimeoutError as exc:
            raise ExampleError(f'{exc}; resume with MEDIA_TASK_REF={task_path}') from exc
        _print_status(result)
    if result.status != ModelStatus.SUCCEEDED:
        details = [part for part in (result.error_code, result.error_message) if part]
        suffix = f': {" - ".join(details)}' if details else ''
        raise ExampleError(f'task finished with status {result.status.value}{suffix}')
    _print_output(result)
    return result


def _print_status(result: ModelResult[Any]) -> None:
    print(f'status: provider={result.provider.value} operation={result.operation.value} status={result.status.value}')


def _print_output(result: ModelResult[Any]) -> None:
    output = result.output
    if isinstance(output, TextOutput):
        print(f'text: {output.text}')
    elif isinstance(output, ImageValidationOutput):
        print(f'image_valid: {str(output.passed).lower()}')
    elif isinstance(output, AvatarListOutput):
        print(f'avatar_count: {len(output.items)}')
        for item in output.items:
            avatar_id = item.get('avatar_id') or item.get('avatar') or item.get('id')
            if avatar_id is not None:
                print(f'avatar_id: {avatar_id}')
    elif isinstance(output, AvatarOutput):
        if output.avatar_id:
            print(f'avatar_id: {output.avatar_id}')
        _print_urls(output.urls)
    elif isinstance(output, AudioOutput):
        _print_urls(output.urls)
        if output.audio_base64:
            _write_audio(result, output)
    elif isinstance(output, MediaOutput):
        _print_urls(output.urls)


def _print_urls(urls) -> None:
    for url in urls:
        print(f'url: {url}')


def _write_audio(result: ModelResult[Any], output: AudioOutput) -> None:
    try:
        data = base64.b64decode(output.audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ExampleError('provider returned invalid Base64 audio') from exc
    suffix = re.sub(r'[^A-Za-z0-9]+', '', output.format or '') or 'bin'
    task_id = result.task_ref.task_id if result.task_ref is not None else 'result'
    safe_id = re.sub(r'[^A-Za-z0-9_.-]+', '_', task_id)
    path = output_dir() / f'{result.provider.value}-{result.operation.value}-{safe_id}.{suffix}'
    path.write_bytes(data)
    print(f'audio_file: {path}')


def run(action) -> int:
    try:
        action()
    except KeyboardInterrupt:
        print('error: interrupted; remote tasks, if any, were not cancelled', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0
