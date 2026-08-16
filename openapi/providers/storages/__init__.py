from __future__ import annotations

from datetime import datetime
from os import PathLike
from typing import Any, BinaryIO, Iterator, Mapping, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from openapi.exceptions import OpenAPIException


class ObjectStorageError(OpenAPIException):
    """Base error shared by all object-storage adapters."""


class ObjectStorageConfigurationError(ObjectStorageError):
    """An object-storage adapter cannot be configured or initialized."""


class ObjectNotFoundError(ObjectStorageError):
    """The requested object does not exist."""


class ObjectMetadata(BaseModel):
    """Provider-neutral metadata returned by object-storage adapters."""

    model_config = ConfigDict(frozen=True)

    key: str
    size: int
    last_modified: Optional[datetime] = None
    etag: Optional[str] = None
    content_type: Optional[str] = None


@runtime_checkable
class ObjectStorageClient(Protocol):
    """Common interface implemented by concrete object-storage adapters."""

    def put_object(self, key: str, content: Any, headers: Mapping[str, str] | None = None) -> str: ...

    def download_to(self, key: str, destination: str | PathLike[str] | BinaryIO) -> None: ...

    def delete_object(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def stat(self, key: str) -> ObjectMetadata: ...

    def iter_objects(self, prefix: str = '', delimiter: str = '') -> Iterator[ObjectMetadata]: ...

    def sign_url(self, key: str, method: str = 'GET', expires: int | None = None) -> str: ...

    def object_url(self, key: str) -> str: ...

    def key_from_url(self, url: str) -> str | None: ...


__all__ = [
    'ObjectMetadata',
    'ObjectNotFoundError',
    'ObjectStorageClient',
    'ObjectStorageConfigurationError',
    'ObjectStorageError',
]
