from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from examples.media_generation import common
from openapi.providers.media_generation import (
    AvatarCloneRequest,
    DigitalHumanRequest,
    FileUploadRequest,
    HiFlyConfig,
    MediaClient,
    MediaOutput,
    ModelProvider,
    ModelResult,
    VoiceCloneRequest,
)

# === 素材来源（URL 和本地路径二选一，URL 优先）===

# 数字人形象 — 图片克隆
AVATAR_IMAGE_URL: Optional[str] = 'https://cdn.example.com/photo.jpg'
AVATAR_IMAGE_PATH: Optional[str] = None  # 本地图片路径，如 '/path/to/photo.jpg'

# 数字人形象 — 视频克隆（与图片互斥，只保留一种；置空 IMAGE_URL/IMAGE_PATH 后启用）
AVATAR_VIDEO_URL: Optional[str] = None
AVATAR_VIDEO_PATH: Optional[str] = None

# 声音样本
VOICE_AUDIO_URL: Optional[str] = 'https://cdn.example.com/sample.wav'
VOICE_AUDIO_PATH: Optional[str] = None  # 本地音频路径，如 '/path/to/sample.wav'

# === 生成参数 ===

AVATAR_TITLE = '我的数字人形象'
VOICE_TITLE = '我的自定义音色'
DIGITAL_HUMAN_TITLE = '数字人视频'
DIGITAL_HUMAN_TEXT = '大家好，欢迎来到我的频道！'
AIGC_FLAG: Optional[int] = None
LANGUAGE = 'zh'
AVATAR_CLONE_MODEL: Optional[int] = None  # None 使用 HiFlyConfig 默认值 2
PARAMETERS: dict = {}


def _resolve_source(
    *, url: Optional[str], path: Optional[str], label: str
) -> Tuple[str, Union[str, Path]]:
    """Return ('url', value) or ('file', Path)."""
    if url:
        return ('url', url)
    if path:
        resolved = Path(path).expanduser()
        if not resolved.is_file():
            raise common.ExampleError(f'{label} file not found: {resolved}')
        return ('file', resolved)
    raise common.ExampleError(
        f'either {label}_URL or {label}_PATH must be set; '
        f'edit the script constants or set matching environment variables'
    )


def _upload(media: MediaClient, path: Path, content_type: str) -> str:
    """Upload a local file to HiFly and return the file_id."""
    print(f'  uploading: {path}')
    data = path.read_bytes()
    ext = path.suffix.lstrip('.') or 'bin'
    result = media.avatar.upload(
        FileUploadRequest(content=data, file_extension=ext, content_type=content_type),
        provider=ModelProvider.HIFLY,
    )
    # upload_file is synchronous — no polling needed
    file_id = result.output.file_id
    print(f'  file_id: {file_id}')
    return file_id


def run(
    media: MediaClient,
    *,
    avatar_image_url: Optional[str],
    avatar_image_path: Optional[str],
    avatar_video_url: Optional[str],
    avatar_video_path: Optional[str],
    voice_audio_url: Optional[str],
    voice_audio_path: Optional[str],
    avatar_title: str,
    voice_title: str,
    digital_human_title: str,
    digital_human_text: str,
    aigc_flag: Optional[int],
    language: str,
    avatar_clone_model: Optional[int],
    parameters: Dict[str, object],
) -> ModelResult[MediaOutput]:
    """Run the full digital human pipeline against an existing MediaClient."""
    # Resolve avatar source: video takes precedence if set, otherwise image
    if avatar_video_url or avatar_video_path:
        avatar_mode, avatar_source = _resolve_source(
            url=avatar_video_url, path=avatar_video_path, label='AVATAR_VIDEO',
        )
        use_video = True
    else:
        avatar_mode, avatar_source = _resolve_source(
            url=avatar_image_url, path=avatar_image_path, label='AVATAR_IMAGE',
        )
        use_video = False

    voice_mode, voice_source = _resolve_source(
        url=voice_audio_url, path=voice_audio_path, label='VOICE_AUDIO',
    )

    # ---- Step 1: Prepare source files ----
    print('=== Step 1: Prepare source files ===')

    if avatar_mode == 'file':
        assert isinstance(avatar_source, Path)
        content_type = 'video/mp4' if use_video else 'image/jpeg'
        avatar_file_id = _upload(media, avatar_source, content_type)
        if use_video:
            avatar_payload: dict = {'video_file_id': avatar_file_id, 'title': avatar_title}
        else:
            avatar_payload = {
                'image_file_id': avatar_file_id,
                'title': avatar_title,
                'model': avatar_clone_model,
            }
    else:
        assert isinstance(avatar_source, str)
        if use_video:
            avatar_payload = {'video_url': avatar_source, 'title': avatar_title}
        else:
            avatar_payload = {
                'image_url': avatar_source,
                'title': avatar_title,
                'model': avatar_clone_model,
            }
        print(f'  using public URL: {avatar_source}')

    if voice_mode == 'file':
        assert isinstance(voice_source, Path)
        voice_file_id = _upload(media, voice_source, 'audio/wav')
        voice_payload: dict = {'file_id': voice_file_id, 'title': voice_title}
    else:
        assert isinstance(voice_source, str)
        voice_payload = {'audio_url': voice_source, 'title': voice_title}
        print(f'  using public URL: {voice_source}')

    # ---- Step 2: Clone avatar ----
    print('=== Step 2: Clone avatar ===')
    if aigc_flag is not None:
        avatar_payload['aigc_flag'] = aigc_flag
    avatar_payload['parameters'] = parameters

    clone_result = media.avatar.clone(
        AvatarCloneRequest(**avatar_payload),
        provider=ModelProvider.HIFLY,
    )
    clone_final = common.complete_result(media, clone_result)
    avatar_id = clone_final.output.avatar_id
    if not avatar_id:
        raise common.ExampleError('avatar clone completed but no avatar_id returned')
    print(f'  avatar_id: {avatar_id}')

    # ---- Step 3: Clone voice ----
    print('=== Step 3: Clone voice ===')
    voice_payload['language'] = language
    voice_payload['parameters'] = parameters

    voice_result = media.speech.clone_voice(
        VoiceCloneRequest(**voice_payload),
        provider=ModelProvider.HIFLY,
    )
    voice_final = common.complete_result(media, voice_result)
    voice_id = voice_final.output.voice_id
    print(f'  voice_id: {voice_id}')

    # ---- Step 4: Generate digital human video ----
    print('=== Step 4: Generate digital human video ===')
    render_request = DigitalHumanRequest(
        avatar=avatar_id,
        text=digital_human_text,
        voice=voice_id,
        title=digital_human_title,
        parameters=parameters,
    )
    render_result = media.avatar.render(render_request, provider=ModelProvider.HIFLY)
    render_final = common.complete_result(media, render_result)
    if render_final.output is None or not render_final.output.urls:
        raise common.ExampleError('digital human task finished without output media')
    return render_final


def execute() -> None:
    use_video = bool(AVATAR_VIDEO_URL or AVATAR_VIDEO_PATH)
    config = HiFlyConfig(
        token=common.env_string('MEDIA_HIFLY_TOKEN', required=True),
        **common.optional_values(
            avatar_clone_model=AVATAR_CLONE_MODEL
            if not use_video and AVATAR_CLONE_MODEL is not None
            else 2,
        ),
    )
    with MediaClient.create(config) as media:
        return run(
            media,
            avatar_image_url=AVATAR_IMAGE_URL,
            avatar_image_path=AVATAR_IMAGE_PATH,
            avatar_video_url=AVATAR_VIDEO_URL,
            avatar_video_path=AVATAR_VIDEO_PATH,
            voice_audio_url=VOICE_AUDIO_URL,
            voice_audio_path=VOICE_AUDIO_PATH,
            avatar_title=AVATAR_TITLE,
            voice_title=VOICE_TITLE,
            digital_human_title=DIGITAL_HUMAN_TITLE,
            digital_human_text=DIGITAL_HUMAN_TEXT,
            aigc_flag=AIGC_FLAG,
            language=LANGUAGE,
            avatar_clone_model=AVATAR_CLONE_MODEL,
            parameters=PARAMETERS,
        )


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
