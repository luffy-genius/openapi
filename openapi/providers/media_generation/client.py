from __future__ import annotations

from pathlib import Path
from typing import BinaryIO, Callable, Optional, Union

import httpx

from openapi.providers.media_generation.domains import (
    AvatarDomain,
    ImageDomain,
    SpeechDomain,
    TaskDomain,
    TextDomain,
    VideoDomain,
)
from openapi.providers.media_generation.models import (
    AliyunConfig,
    DeepSeekConfig,
    DownloadedMedia,
    HiFlyConfig,
    SiliconFlowConfig,
    VolcengineConfig,
)
from openapi.providers.media_generation.registry import ProviderRegistry
from openapi.providers.media_generation.workflows import TranslateToSpeechWorkflow

ProviderConfig = Union[AliyunConfig, DeepSeekConfig, HiFlyConfig, SiliconFlowConfig, VolcengineConfig]


class MediaClient:
    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        http_client: httpx.Client,
        owns_http_client: bool,
        task_sleep: Optional[Callable[[float], None]] = None,
    ):
        self.text = TextDomain(registry)
        self.speech = SpeechDomain(registry)
        self.image = ImageDomain(registry)
        self.video = VideoDomain(registry)
        self.avatar = AvatarDomain(registry)
        self.task = TaskDomain(registry, sleep=task_sleep) if task_sleep is not None else TaskDomain(registry)
        self.workflow = TranslateToSpeechWorkflow(registry)
        self._http_client = http_client
        self._owns_http_client = owns_http_client

    @classmethod
    def create(
        cls,
        *configs: ProviderConfig,
        http_client: Optional[httpx.Client] = None,
        sleep: Optional[Callable[[float], None]] = None,
        timeout: float = 300.0,
    ) -> MediaClient:
        from openapi.providers.media_generation.factory import create_media_client

        return create_media_client(
            *configs,
            http_client=http_client,
            sleep=sleep,
            timeout=timeout,
        )

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def download(self, url: str) -> DownloadedMedia:
        try:
            response = self._http_client.get(url, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            self._raise_download_error(exc)
        content_type = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
        return DownloadedMedia(content=response.content, content_type=content_type or 'application/octet-stream')

    def download_to(self, url: str, destination: Union[str, Path, BinaryIO]) -> None:
        """Stream a media URL to a file path or file-like object without buffering it in memory.

        Local filesystem errors propagate as ``OSError``; remote HTTP and network errors are
        classified into ``ProviderAPIError``.
        """
        try:
            with self._http_client.stream('GET', url, follow_redirects=True) as response:
                response.raise_for_status()
                if hasattr(destination, 'write'):
                    for chunk in response.iter_bytes():
                        destination.write(chunk)
                else:
                    with Path(destination).open('wb') as output:
                        for chunk in response.iter_bytes():
                            output.write(chunk)
        except httpx.HTTPError as exc:
            self._raise_download_error(exc)

    @staticmethod
    def _raise_download_error(exc: httpx.HTTPError) -> None:
        from openapi.providers.media_generation.exceptions import ProviderAPIError, ProviderErrorCode

        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            raise ProviderAPIError.from_provider_response(
                f'media download returned HTTP {status}',
                http_status=status,
            ) from exc
        code = (
            ProviderErrorCode.TIMEOUT
            if isinstance(exc, httpx.TimeoutException)
            else ProviderErrorCode.NETWORK_ERROR
        )
        raise ProviderAPIError(
            f'media download request failed: {type(exc).__name__}',
            code=code,
            retryable=True,
            fallback_allowed=True,
        ) from exc

    def __enter__(self) -> MediaClient:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
