from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from openapi.enums import TextChoices


class ModelProvider(TextChoices):
    VOLCENGINE = 'volcengine'
    ALIYUN = 'aliyun'
    HIFLY = 'hifly'
    DEEPSEEK = 'deepseek'


class ModelStatus(TextChoices):
    QUEUED = 'queued'
    PROCESSING = 'processing'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    EXPIRED = 'expired'
    CANCELED = 'canceled'


class ModelOperation(TextChoices):
    TEXT_OPTIMIZATION = 'text_optimization'
    TEXT_TO_SPEECH = 'text_to_speech'
    TRANSLATE_TO_SPEECH = 'translate_to_speech'
    TEXT_TO_IMAGE = 'text_to_image'
    IMAGE_TO_IMAGE = 'image_to_image'
    IMAGE_TO_VIDEO = 'image_to_video'
    DIGITAL_HUMAN_IMAGE_VALIDATION = 'digital_human_image_validation'
    DIGITAL_HUMAN = 'digital_human'
    AVATAR_CLONE = 'avatar_clone'
    AVATAR_LIST = 'avatar_list'


class TextOptimizationAction(TextChoices):
    POLISH = 'polish'
    EXPAND = 'expand'
    SIMPLIFY = 'simplify'
    TRANSLATE = 'translate'


class TextOptimizationStyle(TextChoices):
    PROFESSIONAL = 'professional'
    FRIENDLY = 'friendly'
    LIVELY = 'lively'
    CONCISE = 'concise'


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
    error_code: Optional[str] = None
    error_message: Optional[str] = None

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
    voice: str
    language: Optional[str] = None
    title: Optional[str] = None
    audio_config: AudioConfig = Field(default_factory=AudioConfig)
    parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('text', 'model', 'voice')
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

    @field_validator('parameters')
    @classmethod
    def protect_request_fields(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        return validate_tts_parameters(value, 'parameters')


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
    prompt: str
    images: List[str] = Field(default_factory=list)
    model: Optional[str] = None
    size: Optional[str] = None
    n: int = 1
    seed: Optional[int] = None
    watermark: Optional[bool] = None
    negative_prompt: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ImageToVideoRequest(BaseModel):
    image: str
    prompt: str = ''
    last_image: Optional[str] = None
    audio_url: Optional[str] = None
    model: Optional[str] = None
    duration: Optional[int] = None
    resolution: Optional[str] = None
    ratio: Optional[str] = None
    seed: Optional[int] = None
    watermark: Optional[bool] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class DigitalHumanRequest(BaseModel):
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    avatar: Optional[str] = None
    text: Optional[str] = None
    voice: Optional[str] = None
    title: Optional[str] = None
    prompt: str = ''
    model: Optional[str] = None
    resolution: Optional[str] = None
    seed: Optional[int] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AvatarCloneRequest(BaseModel):
    title: str = '未命名'
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    model: Optional[int] = None
    aigc_flag: Optional[int] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


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
