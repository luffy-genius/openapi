from __future__ import annotations

import importlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from os import PathLike
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping, Optional
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from openapi.providers.storages import (
    ObjectMetadata,
    ObjectNotFoundError,
    ObjectStorageConfigurationError,
    ObjectStorageError,
)


class OSSProviderError(ObjectStorageError):
    """Base error raised by the Aliyun OSS provider."""


class OSSConfigurationError(OSSProviderError, ObjectStorageConfigurationError):
    """The OSS client is missing a dependency or has invalid configuration."""


class OSSObjectNotFoundError(OSSProviderError, ObjectNotFoundError):
    """The requested OSS object does not exist."""


class OSSConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_key_id: SecretStr
    access_key_secret: SecretStr
    endpoint: str
    region: str
    bucket_name: str
    public_endpoint: Optional[str] = None
    public_base_url: Optional[str] = None
    sign_expires: int = Field(default=3600, gt=0)

    @field_validator('access_key_id', 'access_key_secret')
    @classmethod
    def require_nonempty_secret(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError('must not be empty')
        return value

    @field_validator('endpoint', 'region', 'bucket_name')
    @classmethod
    def require_nonempty_string(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('must not be empty')
        return value.strip()

    @field_validator('public_endpoint', 'public_base_url')
    @classmethod
    def reject_empty_optional_string(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError('must not be empty')
        return value.strip() if value is not None else None


class Client:
    def __init__(self, config: OSSConfig):
        self.config = config
        self._endpoint = _normalise_endpoint(config.endpoint, 'endpoint')
        public_endpoint = config.public_endpoint or _derive_public_endpoint(self._endpoint)
        self._public_endpoint = _normalise_endpoint(public_endpoint, 'public_endpoint')
        self._public_base_url = (
            _normalise_base_url(config.public_base_url, 'public_base_url') if config.public_base_url else None
        )

        try:
            oss2 = importlib.import_module('oss2')
        except ModuleNotFoundError as exc:
            if exc.name != 'oss2':
                raise OSSConfigurationError('Failed to import the oss2 dependency') from exc
            raise OSSConfigurationError(
                "Aliyun OSS support is not installed; run: pip install 'openapipy[aliyun-oss]'"
            ) from exc
        except Exception as exc:
            raise OSSConfigurationError('Failed to import the oss2 dependency') from exc

        try:
            credentials = oss2.credentials.StaticCredentialsProvider(
                config.access_key_id.get_secret_value(),
                config.access_key_secret.get_secret_value(),
            )
            auth = oss2.ProviderAuthV4(credentials)
            self._bucket = oss2.Bucket(
                auth,
                self._endpoint,
                config.bucket_name,
                region=config.region,
            )
            self._public_bucket = oss2.Bucket(
                auth,
                self._public_endpoint,
                config.bucket_name,
                region=config.region,
            )
        except Exception as exc:
            raise OSSConfigurationError('Failed to initialize the Aliyun OSS client') from exc

    def put_object(self, key: str, content: Any, headers: Mapping[str, str] | None = None) -> str:
        try:
            self._bucket.put_object(key, content, headers=headers)
        except Exception as exc:
            self._raise_provider_error('upload', key, exc)
        return key

    def download_to(self, key: str, destination: str | PathLike[str] | BinaryIO) -> None:
        try:
            response = self._bucket.get_object(key)
        except Exception as exc:
            self._raise_provider_error('download', key, exc)
        try:
            if hasattr(destination, 'write'):
                self._copy_stream(response, destination, key)
            else:
                # Local filesystem errors propagate as OSError; only remote read failures
                # are attributed to the provider.
                with Path(destination).open('wb') as output:
                    self._copy_stream(response, output, key)
        finally:
            response.close()

    def delete_object(self, key: str) -> None:
        try:
            self._bucket.delete_object(key)
        except Exception as exc:
            if _is_not_found(exc):
                return
            self._raise_provider_error('delete', key, exc)

    def exists(self, key: str) -> bool:
        try:
            return bool(self._bucket.object_exists(key))
        except Exception as exc:
            if _is_not_found(exc):
                return False
            self._raise_provider_error('check', key, exc)

    def stat(self, key: str) -> ObjectMetadata:
        try:
            result = self._bucket.head_object(key)
            return _metadata_from_sdk(key, result)
        except Exception as exc:
            self._raise_provider_error('stat', key, exc)

    def iter_objects(self, prefix: str = '', delimiter: str = '') -> Iterator[ObjectMetadata]:
        continuation_token = ''
        while True:
            try:
                result = self._bucket.list_objects_v2(
                    prefix=prefix,
                    delimiter=delimiter,
                    continuation_token=continuation_token,
                )
                objects = result.object_list
            except Exception as exc:
                self._raise_provider_error('list', prefix, exc)

            for item in objects:
                try:
                    yield _metadata_from_sdk(item.key, item)
                except Exception as exc:
                    self._raise_provider_error('parse listing for', item.key, exc)

            if not result.is_truncated:
                return
            next_token = result.next_continuation_token
            if not next_token or next_token == continuation_token:
                raise OSSProviderError('Aliyun OSS returned an invalid continuation token')
            continuation_token = next_token

    def sign_url(self, key: str, method: str = 'GET', expires: int | None = None) -> str:
        duration = self.config.sign_expires if expires is None else expires
        if duration <= 0:
            raise OSSConfigurationError('expires must be a positive integer')
        if not method or not method.strip():
            raise OSSConfigurationError('method must not be empty')
        try:
            return self._public_bucket.sign_url(method.upper(), key, duration, slash_safe=True)
        except Exception as exc:
            self._raise_provider_error('sign URL for', key, exc)

    def object_url(self, key: str) -> str:
        base_url = self._public_base_url or _bucket_base_url(self._public_endpoint, self.config.bucket_name)
        return f'{base_url}/{quote(key, safe="/")}'

    def key_from_url(self, url: str) -> str | None:
        try:
            parsed = urlsplit(url)
        except (TypeError, ValueError):
            return None
        if parsed.scheme.lower() not in {'http', 'https'} or not parsed.netloc:
            return None

        bases = [_bucket_base_url(self._public_endpoint, self.config.bucket_name)]
        if self._public_base_url:
            bases.insert(0, self._public_base_url)
        for base_url in bases:
            key = _key_below_base(parsed, base_url)
            if key is not None:
                return key
        return None

    @staticmethod
    def _raise_provider_error(action: str, key: str, exc: Exception) -> None:
        if _is_not_found(exc):
            raise OSSObjectNotFoundError(f'Aliyun OSS object not found: {key}') from exc
        raise OSSProviderError(f'Failed to {action} Aliyun OSS object: {key}') from exc

    @classmethod
    def _copy_stream(cls, source: Any, target: BinaryIO, key: str) -> None:
        """Copy the remote stream, attributing only remote read failures to the provider."""
        while True:
            try:
                chunk = source.read(64 * 1024)
            except Exception as exc:
                cls._raise_provider_error('download', key, exc)
            if not chunk:
                return
            target.write(chunk)


def _normalise_endpoint(value: str, field_name: str) -> str:
    candidate = value.strip()
    if '://' not in candidate:
        candidate = f'https://{candidate}'
    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise OSSConfigurationError(f'{field_name} must be a valid HTTP(S) endpoint') from exc
    if (
        parsed.scheme.lower() not in {'http', 'https'}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {'', '/'}
    ):
        raise OSSConfigurationError(f'{field_name} must be a valid HTTP(S) endpoint')
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, '', '', ''))


def _normalise_base_url(value: str, field_name: str) -> str:
    candidate = value.strip()
    if '://' not in candidate:
        candidate = f'https://{candidate}'
    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise OSSConfigurationError(f'{field_name} must be a valid HTTP(S) URL') from exc
    if (
        parsed.scheme.lower() not in {'http', 'https'}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise OSSConfigurationError(f'{field_name} must be a valid HTTP(S) URL')
    path = parsed.path.rstrip('/')
    return urlunsplit((parsed.scheme.lower(), parsed.netloc, path, '', ''))


def _derive_public_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    hostname = parsed.hostname or ''
    if not hostname.endswith(('-internal.aliyuncs.com', '-internal.aliyuncs.com.cn')):
        return endpoint
    public_netloc = parsed.netloc.replace('-internal.aliyuncs.com', '.aliyuncs.com', 1)
    return urlunsplit((parsed.scheme, public_netloc, parsed.path, '', ''))


def _bucket_base_url(endpoint: str, bucket_name: str) -> str:
    parsed = urlsplit(endpoint)
    return urlunsplit((parsed.scheme, f'{bucket_name}.{parsed.netloc}', '', '', ''))


def _key_below_base(parsed_url: Any, base_url: str) -> str | None:
    parsed_base = urlsplit(base_url)
    same_origin = (
        parsed_url.scheme.lower() == parsed_base.scheme.lower()
        and parsed_url.netloc.lower() == parsed_base.netloc.lower()
    )
    if not same_origin:
        return None
    path = unquote(parsed_url.path)
    base_path = unquote(parsed_base.path).rstrip('/')
    prefix = f'{base_path}/' if base_path else '/'
    if not path.startswith(prefix):
        return None
    key = path[len(prefix) :]
    return key or None


def _metadata_from_sdk(key: str, value: Any) -> ObjectMetadata:
    size = getattr(value, 'content_length', None)
    if size is None:
        size = value.size
    return ObjectMetadata(
        key=key,
        size=int(size),
        last_modified=_normalise_datetime(getattr(value, 'last_modified', None)),
        etag=getattr(value, 'etag', None),
        content_type=getattr(value, 'content_type', None),
    )


def _normalise_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            parsed = parsedate_to_datetime(value)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    raise TypeError(f'unsupported last_modified value: {type(value).__name__}')


def _is_not_found(exc: Exception) -> bool:
    return getattr(exc, 'status', None) == 404 or getattr(exc, 'code', None) in {'NoSuchKey', 'NoSuchObject'}


__all__ = [
    'Client',
    'OSSConfig',
    'OSSConfigurationError',
    'OSSObjectNotFoundError',
    'OSSProviderError',
]
