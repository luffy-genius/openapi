from __future__ import annotations

from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from openapi.enums import TextChoices
from openapi.providers.media_generation.exceptions import ProviderErrorCode


class ModelProvider(TextChoices):
    VOLCENGINE = 'volcengine', '火山引擎'
    ALIYUN = 'aliyun', '阿里云百炼'
    HIFLY = 'hifly', '飞影 HiFly'
    DEEPSEEK = 'deepseek', 'DeepSeek'
    SILICONFLOW = 'siliconflow', 'SiliconFlow'


class ModelStatus(TextChoices):
    QUEUED = 'queued', '排队中'
    PROCESSING = 'processing', '处理中'
    SUCCEEDED = 'succeeded', '已成功'
    FAILED = 'failed', '已失败'
    EXPIRED = 'expired', '已过期'
    CANCELED = 'canceled', '已取消'


class ModelOperation(TextChoices):
    TEXT_OPTIMIZATION = 'text_optimization', '文本优化'
    TEXT_TO_SPEECH = 'text_to_speech', '文本转语音'
    SPEECH_TO_TEXT = 'speech_to_text', '语音转文字'
    VOICE_CLONE = 'voice_clone', '声音复刻'
    VOICE_DESIGN = 'voice_design', '音色设计'
    TRANSLATE_TO_SPEECH = 'translate_to_speech', '翻译后转语音'
    TEXT_TO_IMAGE = 'text_to_image', '文生图'
    IMAGE_TO_IMAGE = 'image_to_image', '图生图'
    IMAGE_TO_VIDEO = 'image_to_video', '图生视频'
    DIGITAL_HUMAN_IMAGE_VALIDATION = 'digital_human_image_validation', '数字人图片校验'
    DIGITAL_HUMAN = 'digital_human', '数字人生成'
    AVATAR_CLONE = 'avatar_clone', '形象克隆'
    AVATAR_LIST = 'avatar_list', '形象列表'
    VOICE_LIST = 'voice_list', '声音列表'
    FILE_UPLOAD = 'file_upload', '文件上传'


class TextOptimizationAction(TextChoices):
    POLISH = 'polish', '润色'
    EXPAND = 'expand', '扩写'
    SIMPLIFY = 'simplify', '简化'
    TRANSLATE = 'translate', '翻译'


class TextOptimizationStyle(TextChoices):
    PROFESSIONAL = 'professional', '专业'
    FRIENDLY = 'friendly', '友好'
    LIVELY = 'lively', '生动'
    CONCISE = 'concise', '简洁'


class TaskRef(BaseModel):
    provider: ModelProvider
    operation: ModelOperation
    task_id: str
    model: Optional[str] = None

    @field_validator('operation', mode='before')
    @classmethod
    def restore_legacy_operation(cls, value):
        # The prerelease media gateway persisted Aliyun image tasks with this value.
        if value == 'image_generation':
            return ModelOperation.TEXT_TO_IMAGE
        return value

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, value: str) -> 'TaskRef':
        return cls.model_validate_json(value)


class TextOutput(BaseModel):
    text: str


class MediaOutput(BaseModel):
    urls: List[str] = Field(default_factory=list)


class AudioOutput(BaseModel):
    urls: List[str] = Field(default_factory=list)
    audio_base64: Optional[str] = None
    format: Optional[str] = None
    sample_rate: Optional[int] = None
    duration_ms: Optional[int] = None
    subtitles: List[Dict[str, Any]] = Field(default_factory=list)


class VoiceOutput(BaseModel):
    voice_id: str
    model: Optional[str] = None
    request_id: Optional[str] = None
    preview_audio: Optional[AudioOutput] = None


class VoiceListOutput(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)
    page: int
    size: int


class FileUploadOutput(BaseModel):
    file_id: str


class DownloadedMedia(BaseModel):
    content: bytes
    content_type: str = 'application/octet-stream'


class ImageValidationOutput(BaseModel):
    passed: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class AvatarOutput(BaseModel):
    avatar_id: Optional[str] = None
    urls: List[str] = Field(default_factory=list)


class AvatarListOutput(BaseModel):
    items: List[Dict[str, Any]] = Field(default_factory=list)
    page: int
    size: int


OutputT = TypeVar('OutputT', bound=BaseModel)


class ModelResult(BaseModel, Generic[OutputT]):
    provider: ModelProvider
    operation: ModelOperation
    status: ModelStatus
    model: Optional[str] = None
    task_ref: Optional[TaskRef] = None
    output: Optional[OutputT] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    error_kind: Optional[ProviderErrorCode] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    fallback_allowed: bool = False

    @property
    def done(self) -> bool:
        return self.status in {
            ModelStatus.SUCCEEDED,
            ModelStatus.FAILED,
            ModelStatus.EXPIRED,
            ModelStatus.CANCELED,
        }


class TextOptimizationRequest(BaseModel):
    text: str
    model: str
    action: TextOptimizationAction = TextOptimizationAction.POLISH
    style: Optional[TextOptimizationStyle] = None
    target_language: Optional[str] = None
    instruction: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('text', 'model')
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be empty')
        return value

    @field_validator('target_language')
    @classmethod
    def reject_empty_target_language(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError('target_language must not be empty')
        return value

    @field_validator('parameters')
    @classmethod
    def protect_request_fields(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        reserved = {'model', 'messages', 'stream'}.intersection(value)
        if reserved:
            fields = ', '.join(sorted(reserved))
            raise ValueError(f'parameters must not override reserved fields: {fields}')
        return value

    @model_validator(mode='after')
    def validate_target_language(self):
        if self.action == TextOptimizationAction.TRANSLATE and self.target_language is None:
            raise ValueError('target_language is required for translate')
        if self.action != TextOptimizationAction.TRANSLATE and self.target_language is not None:
            raise ValueError('target_language is only allowed for translate')
        return self


TTS_RESERVED_FIELDS = {
    'text',
    'model',
    'voice',
    'language',
    'audio_config',
    'format',
    'sample_rate',
    'speech_rate',
    'loudness_rate',
    'pitch_rate',
    'enable_subtitle',
    'watermark',
}


def validate_tts_parameters(value: Dict[str, Any], field_name: str) -> Dict[str, Any]:
    reserved = TTS_RESERVED_FIELDS.intersection(value)
    if reserved:
        fields = ', '.join(sorted(reserved))
        raise ValueError(f'{field_name} must not override reserved fields: {fields}')
    return value


class AudioConfig(BaseModel):
    format: Optional[str] = None
    sample_rate: Optional[int] = None
    speech_rate: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    loudness_rate: Optional[float] = Field(default=None, ge=0.1, le=2.0)
    pitch_rate: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    enable_subtitle: Optional[bool] = None
    watermark: Optional[Dict[str, Any]] = None

    @field_validator('format')
    @classmethod
    def reject_empty_format(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError('format must not be empty')
        return value

    @field_validator('sample_rate')
    @classmethod
    def validate_sample_rate(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value not in {8000, 16000, 24000, 32000, 40000, 44100, 48000}:
            raise ValueError('sample_rate is not supported by the common audio configuration')
        return value


class TextToSpeechRequest(BaseModel):
    text: str
    model: str
    voice: str = ''
    language: Optional[str] = None
    title: Optional[str] = None
    audio_config: AudioConfig = Field(default_factory=AudioConfig)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reference_audio: Optional[bytes] = None
    reference_content_type: Optional[str] = None
    reference_text: Optional[str] = None

    @field_validator('text', 'model')
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be empty')
        return value

    @field_validator('language')
    @classmethod
    def reject_empty_language(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError('language must not be empty')
        return value

    @field_validator('reference_text')
    @classmethod
    def reject_empty_reference_text(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError('reference_text must not be empty')
        return value

    @model_validator(mode='after')
    def reject_conflicting_voice_sources(self):
        if self.reference_audio is not None and self.voice.strip():
            raise ValueError('voice and reference_audio are mutually exclusive')
        return self

    @field_validator('parameters')
    @classmethod
    def protect_request_fields(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return validate_tts_parameters(value, 'parameters')


class SpeechTranscriptionRequest(BaseModel):
    # The Paraformer HTTP API supports only 1 URL per request.
    file_urls: List[str] = Field(max_length=1)
    model: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('file_urls')
    @classmethod
    def require_file_urls(cls, value: List[str]) -> List[str]:
        if not value or any(not item.strip() for item in value):
            raise ValueError('file_urls must contain at least one nonempty URL')
        return value

    @field_validator('model')
    @classmethod
    def reject_empty_model(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError('model must not be empty')
        return value

    @field_validator('parameters')
    @classmethod
    def protect_parameters(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        reserved = {'model', 'input', 'parameters'}.intersection(value)
        if reserved:
            raise ValueError(f'parameters must not override reserved fields: {", ".join(sorted(reserved))}')
        return value


class VoiceCloneRequest(BaseModel):
    audio_url: Optional[str] = None
    file_id: Optional[str] = None
    prefix: str = 'voice'
    title: str = '未命名声音'
    language: Optional[str] = None
    target_model: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def require_source(self):
        if bool(self.audio_url) == bool(self.file_id):
            raise ValueError('exactly one of audio_url and file_id is required')
        return self


class VoiceDesignRequest(BaseModel):
    prompt: str
    preview_text: str
    prefix: str = 'voice'
    language: str = 'zh'
    target_model: Optional[str] = None
    response_format: str = 'wav'
    sample_rate: int = 24000
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('prompt', 'preview_text', 'prefix', 'language', 'response_format')
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be empty')
        return value


class FileUploadRequest(BaseModel):
    content: bytes
    file_extension: str
    content_type: str = 'application/octet-stream'

    @field_validator('content')
    @classmethod
    def require_content(cls, value: bytes) -> bytes:
        if not value:
            raise ValueError('content must not be empty')
        return value

    @field_validator('file_extension')
    @classmethod
    def normalize_extension(cls, value: str) -> str:
        normalized = value.strip().lstrip('.')
        if not normalized:
            raise ValueError('file_extension must not be empty')
        return normalized


class TranslateToSpeechRequest(BaseModel):
    text: str
    target_language: str
    translation_model: str
    speech_model: str
    voice: str
    source_language: Optional[str] = None
    title: Optional[str] = None
    audio_config: AudioConfig = Field(default_factory=AudioConfig)
    translation_parameters: Dict[str, Any] = Field(default_factory=dict)
    speech_parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('text', 'target_language', 'translation_model', 'speech_model', 'voice')
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be empty')
        return value

    @field_validator('source_language')
    @classmethod
    def reject_empty_source_language(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError('source_language must not be empty')
        return value

    @field_validator('translation_parameters')
    @classmethod
    def protect_translation_fields(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        reserved = {'model', 'messages', 'stream'}.intersection(value)
        if reserved:
            fields = ', '.join(sorted(reserved))
            raise ValueError(f'translation_parameters must not override reserved fields: {fields}')
        return value

    @field_validator('speech_parameters')
    @classmethod
    def protect_speech_fields(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return validate_tts_parameters(value, 'speech_parameters')


class ImageGenerationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    prompt: str = Field(min_length=1, max_length=4000)
    images: List[str] = Field(default_factory=list, max_length=9)
    model: Optional[str] = None
    size: Optional[str] = None
    n: int = Field(default=1, ge=1, le=4)
    seed: Optional[int] = Field(default=None, ge=0)
    watermark: Optional[bool] = None
    negative_prompt: Optional[str] = Field(default=None, max_length=2000)
    strength: Optional[float] = Field(default=None, ge=0, le=1)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('prompt')
    @classmethod
    def require_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('prompt must not be empty')
        return value

    @field_validator('images')
    @classmethod
    def require_nonempty_images(cls, value: List[str]) -> List[str]:
        if any(not item.strip() for item in value):
            raise ValueError('images must not contain empty values')
        return value

    @field_validator('model', 'size')
    @classmethod
    def reject_empty_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError('must not be empty')
        return value

    @field_validator('parameters')
    @classmethod
    def protect_parameters(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        reserved = {
            'image',
            'images',
            'input',
            'messages',
            'model',
            'n',
            'negative_prompt',
            'prompt',
            'seed',
            'size',
            'strength',
            'watermark',
        }.intersection(value)
        if reserved:
            raise ValueError(f'parameters must not override reserved fields: {", ".join(sorted(reserved))}')
        return value


class ImageToVideoRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image: str = Field(min_length=1)
    prompt: str = Field(default='', max_length=4000)
    last_image: Optional[str] = None
    audio_url: Optional[str] = None
    model: Optional[str] = None
    duration: Optional[int] = Field(default=None, ge=2, le=15)
    resolution: Optional[Literal['720P', '1080P']] = None
    ratio: Optional[Literal['auto', '16:9', '9:16', '1:1', '4:3', '3:4']] = None
    seed: Optional[int] = Field(default=None, ge=0)
    watermark: Optional[bool] = None
    negative_prompt: str = Field(default='', max_length=2000)
    prompt_extend: Optional[bool] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('image')
    @classmethod
    def require_image(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('image must not be empty')
        return value

    @field_validator('last_image', 'audio_url', 'model')
    @classmethod
    def reject_empty_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError('must not be empty')
        return value

    @field_validator('parameters')
    @classmethod
    def protect_parameters(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        reserved = {
            'audio_url',
            'content',
            'duration',
            'image',
            'input',
            'last_image',
            'media',
            'model',
            'negative_prompt',
            'prompt',
            'prompt_extend',
            'ratio',
            'resolution',
            'seed',
            'watermark',
        }.intersection(value)
        if reserved:
            raise ValueError(f'parameters must not override reserved fields: {", ".join(sorted(reserved))}')
        return value


class DigitalHumanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    file_id: Optional[str] = None
    avatar: Optional[str] = None
    text: Optional[str] = None
    voice: Optional[str] = None
    title: Optional[str] = None
    prompt: str = ''
    model: Optional[str] = None
    resolution: Optional[Literal['720P', '1080P']] = None
    ratio: Optional[Literal['16:9', '9:16', '1:1']] = None
    seed: Optional[int] = Field(default=None, ge=0)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('parameters')
    @classmethod
    def protect_parameters(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        reserved = {
            'audio_url',
            'avatar',
            'file_id',
            'image_url',
            'model',
            'pipeline',
            'prompt',
            'ratio',
            'resolution',
            'seed',
            'text',
            'title',
            'voice',
        }.intersection(value)
        if reserved:
            raise ValueError(f'parameters must not override reserved fields: {", ".join(sorted(reserved))}')
        return value


class AvatarCloneRequest(BaseModel):
    title: str = '未命名'
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    image_file_id: Optional[str] = None
    video_file_id: Optional[str] = None
    model: Optional[int] = None
    aigc_flag: Optional[int] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('model', mode='before')
    @classmethod
    def coerce_model(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip().isdigit():
            return int(value)
        return value

    @model_validator(mode='after')
    def require_single_source(self):
        sources = [self.image_url, self.video_url, self.image_file_id, self.video_file_id]
        if sum(bool(item) for item in sources) != 1:
            raise ValueError(
                'exactly one of image_url, image_file_id, video_url and video_file_id is required for avatar cloning'
            )
        return self


class VolcengineSpeechConfig(BaseModel):
    app_id: str
    access_token: SecretStr
    base_url: str = 'https://openspeech.bytedance.com/api/v1/tts'

    @field_validator('app_id')
    @classmethod
    def require_app_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('app_id must not be empty')
        return value

    @field_validator('access_token')
    @classmethod
    def require_access_token(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError('access_token must not be empty')
        return value

    @field_validator('base_url')
    @classmethod
    def require_https(cls, value: str) -> str:
        value = value.rstrip('/')
        if not value.startswith('https://'):
            raise ValueError('base_url must use HTTPS')
        return value


class VolcengineConfig(BaseModel):
    ark_api_key: Optional[SecretStr] = None
    access_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None
    image_model: str = 'doubao-seedream-4-5-251128'
    video_model: str = 'doubao-seedance-2-0-260128'
    digital_human_model: str = 'jimeng_realman_avatar_picture_omni_v15'
    speech: Optional[VolcengineSpeechConfig] = None

    @model_validator(mode='after')
    def require_credentials(self):
        ark = self.ark_api_key.get_secret_value() if self.ark_api_key is not None else ''
        access = self.access_key.get_secret_value() if self.access_key is not None else ''
        secret = self.secret_key.get_secret_value() if self.secret_key is not None else ''
        if not ark and not access and not secret and self.speech is None:
            raise ValueError('ark_api_key, speech, or both access_key and secret_key are required')
        if bool(access) != bool(secret):
            raise ValueError('access_key and secret_key must be configured together')
        if self.ark_api_key is not None and not ark:
            raise ValueError('ark_api_key must not be empty')
        if self.access_key is not None and not access:
            raise ValueError('access_key must not be empty')
        if self.secret_key is not None and not secret:
            raise ValueError('secret_key must not be empty')
        return self


class AliyunConfig(BaseModel):
    api_key: SecretStr
    workspace_id: Optional[str] = None
    region: str = 'cn-beijing'
    image_model: str = 'wan2.7-image-pro'
    video_model: str = 'wan2.7-i2v-2026-04-25'
    digital_human_model: str = 'wan2.2-s2v'
    custom_voice_model: str = 'cosyvoice-v3.5-flash'
    asr_model: str = 'paraformer-v1'

    @field_validator('api_key')
    @classmethod
    def require_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError('api_key must not be empty')
        return value


class HiFlyConfig(BaseModel):
    token: SecretStr
    avatar_clone_model: int = 2

    @field_validator('token')
    @classmethod
    def require_token(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError('token must not be empty')
        return value


class DeepSeekConfig(BaseModel):
    api_key: SecretStr
    base_url: str = 'https://api.deepseek.com'

    @field_validator('base_url')
    @classmethod
    def require_https(cls, value: str) -> str:
        value = value.rstrip('/')
        if not value.startswith('https://'):
            raise ValueError('base_url must use HTTPS')
        return value

    @field_validator('api_key')
    @classmethod
    def require_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError('api_key must not be empty')
        return value


class SiliconFlowConfig(BaseModel):
    api_key: SecretStr
    base_url: str = 'https://api.siliconflow.cn/v1'
    default_voice: str = ''
    response_format: str = 'mp3'
    sample_rate: int = 44100
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    gain: float = Field(default=0.0, ge=-10.0, le=10.0)

    @field_validator('api_key')
    @classmethod
    def require_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError('api_key must not be empty')
        return value

    @field_validator('base_url')
    @classmethod
    def require_https(cls, value: str) -> str:
        value = value.rstrip('/')
        if not value.startswith('https://'):
            raise ValueError('base_url must use HTTPS')
        return value
