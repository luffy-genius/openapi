import re
from dataclasses import dataclass
from typing import Optional

from openapi.enums import TextChoices
from openapi.exceptions import OpenAPIException


class MediaGenerationError(OpenAPIException):
    """Base exception for the media generation SDK."""


class ConfigurationError(MediaGenerationError):
    """A requested provider or credential has not been configured."""


class UnsupportedCapabilityError(MediaGenerationError):
    """The selected provider does not implement the requested operation."""


class ProviderErrorCode(TextChoices):
    NETWORK_ERROR = 'PROVIDER_NETWORK_ERROR', '供应商网络错误'
    TIMEOUT = 'PROVIDER_TIMEOUT', '供应商超时'
    AUTH_FAILED = 'PROVIDER_AUTH_FAILED', '供应商鉴权失败'
    RATE_LIMITED = 'PROVIDER_RATE_LIMITED', '供应商限流'
    SERVICE_UNAVAILABLE = 'PROVIDER_SERVICE_UNAVAILABLE', '供应商服务不可用'
    CONTENT_REJECTED = 'CONTENT_REJECTED', '内容安全拒绝'
    INVALID_INPUT = 'INVALID_INPUT', '非法输入'
    OWNERSHIP_ERROR = 'OWNERSHIP_ERROR', '资源所有权错误'
    INVALID_RESPONSE = 'PROVIDER_INVALID_RESPONSE', '供应商响应无效'
    UNKNOWN = 'PROVIDER_UNKNOWN_ERROR', '未知供应商错误'


@dataclass(frozen=True)
class ProviderErrorClassification:
    code: ProviderErrorCode
    retryable: bool = False
    fallback_allowed: bool = False


def _normalise_classification_text(value: str) -> str:
    """Fold camelCase, kebab-case, snake_case and spaced text into one underscore form."""
    snake = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', value)
    return re.sub(r'[_\-\s]+', '_', snake).lower()


def classify_provider_error(
    *,
    provider_code: Optional[str] = None,
    message: str = '',
    http_status: Optional[int] = None,
) -> ProviderErrorClassification:
    """Classify failures conservatively for application-level retry and fallback."""

    text = _normalise_classification_text(f'{provider_code or ""} {message}')
    if any(
        marker in text
        for marker in (
            'content_policy',
            'content_safety',
            'content_filter',
            'contentsafety',
            'contentfilter',
            'data_inspection_failed',
            'inappropriate',
            'moderation',
            'sensitive',
            'risk_control',
            '内容安全',
            '敏感',
            '审核拒绝',
        )
    ):
        return ProviderErrorClassification(ProviderErrorCode.CONTENT_REJECTED)
    if any(
        marker in text
        for marker in ('ownership', 'not_owner', 'permission_denied', 'permissiondenied', '无权使用', '归属')
    ):
        return ProviderErrorClassification(ProviderErrorCode.OWNERSHIP_ERROR)
    if http_status in {401, 403} or any(
        marker in text
        for marker in (
            'unauthorized',
            'authentication',
            'invalid_api_key',
            'invalid_token',
            'invalidapikey',
            'invalidtoken',
            'accessdenied',
        )
    ):
        return ProviderErrorClassification(ProviderErrorCode.AUTH_FAILED, fallback_allowed=True)
    if http_status == 429 or any(
        marker in text for marker in ('rate_limit', 'ratelimit', 'throttl', 'too_many_requests')
    ):
        return ProviderErrorClassification(
            ProviderErrorCode.RATE_LIMITED,
            retryable=True,
            fallback_allowed=True,
        )
    if http_status is not None and 500 <= http_status < 600:
        return ProviderErrorClassification(
            ProviderErrorCode.SERVICE_UNAVAILABLE,
            retryable=True,
            fallback_allowed=True,
        )
    if any(
        marker in text
        for marker in (
            'service_unavailable',
            'serviceunavailable',
            'internal_error',
            'internalerror',
            'system_error',
            'systemerror',
            'overloaded',
        )
    ):
        return ProviderErrorClassification(
            ProviderErrorCode.SERVICE_UNAVAILABLE,
            retryable=True,
            fallback_allowed=True,
        )
    if http_status in {400, 404, 409, 413, 415, 422} or any(
        marker in text
        for marker in ('invalid_parameter', 'invalidparameter', 'invalid_argument', 'invalidargument', 'bad_request')
    ):
        return ProviderErrorClassification(ProviderErrorCode.INVALID_INPUT)
    return ProviderErrorClassification(ProviderErrorCode.UNKNOWN)


class ProviderAPIError(MediaGenerationError):
    """A normalized provider failure with machine-readable routing guidance."""

    def __init__(
        self,
        message: str,
        *,
        code: ProviderErrorCode = ProviderErrorCode.UNKNOWN,
        provider_code: Optional[str] = None,
        http_status: Optional[int] = None,
        retryable: bool = False,
        fallback_allowed: bool = False,
        remote_task_may_exist: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.provider_code = provider_code
        self.http_status = http_status
        self.retryable = retryable
        self.fallback_allowed = fallback_allowed
        self.remote_task_may_exist = remote_task_may_exist

    @classmethod
    def from_provider_response(
        cls,
        message: str,
        *,
        provider_code: Optional[str] = None,
        http_status: Optional[int] = None,
        remote_task_may_exist: bool = False,
    ) -> 'ProviderAPIError':
        classification = classify_provider_error(
            provider_code=provider_code,
            message=message,
            http_status=http_status,
        )
        fallback_allowed = classification.fallback_allowed and not remote_task_may_exist
        return cls(
            message,
            code=classification.code,
            provider_code=provider_code,
            http_status=http_status,
            retryable=classification.retryable,
            fallback_allowed=fallback_allowed,
            remote_task_may_exist=remote_task_may_exist,
        )

    def with_message(self, message: str) -> 'ProviderAPIError':
        """Return a copy with a new message, preserving all routing metadata."""
        return type(self)(
            message,
            code=self.code,
            provider_code=self.provider_code,
            http_status=self.http_status,
            retryable=self.retryable,
            fallback_allowed=self.fallback_allowed,
            remote_task_may_exist=self.remote_task_may_exist,
        )


class GenerationTimeoutError(MediaGenerationError):
    """Polling exceeded the local timeout; the remote task is not cancelled."""
