from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

import httpx

from openapi.providers.media_generation.exceptions import ProviderAPIError, ProviderErrorCode


class ProviderTransport:
    max_query_retries = 3

    def __init__(
        self,
        http_client: httpx.Client,
        *,
        provider_name: str,
        secrets: Iterable[str] = (),
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.http_client = http_client
        self.provider_name = provider_name
        self.secrets = tuple(value for value in secrets if value)
        self.sleep = sleep

    def redact(self, text: Any) -> str:
        result = str(text)
        for value in self.secrets:
            result = result.replace(value, '**********')
        return result

    def request(
        self,
        method: str,
        url: str,
        *,
        query: bool = False,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        capture_response_headers: bool = False,
        remote_task_may_exist: bool = False,
    ) -> Dict[str, Any]:
        response = self.request_response(
            method,
            url,
            query=query,
            headers=headers,
            params=params,
            json_body=json_body,
            remote_task_may_exist=remote_task_may_exist,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            remote_task_may_exist = remote_task_may_exist or self._unsafe_mutation(method, query)
            raise ProviderAPIError(
                f'{self.provider_name} API returned invalid JSON',
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=query,
                remote_task_may_exist=remote_task_may_exist,
            ) from exc
        if not isinstance(payload, dict):
            remote_task_may_exist = remote_task_may_exist or self._unsafe_mutation(method, query)
            raise ProviderAPIError(
                f'{self.provider_name} API returned an invalid response object',
                code=ProviderErrorCode.INVALID_RESPONSE,
                retryable=query,
                remote_task_may_exist=remote_task_may_exist,
            )
        if capture_response_headers:
            payload['_response_headers'] = {
                key: value
                for key, value in response.headers.items()
                if key.lower() in {'x-tt-logid', 'x-request-id', 'request-id'}
            }
        return payload

    def request_response(
        self,
        method: str,
        url: str,
        *,
        query: bool = False,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        content: Optional[bytes] = None,
        files: Optional[Mapping[str, Any]] = None,
        follow_redirects: bool = False,
        remote_task_may_exist: bool = False,
    ) -> httpx.Response:
        attempts = self.max_query_retries + 1 if query else 1
        response = None
        for attempt in range(attempts):
            try:
                response = self.http_client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    content=content,
                    files=files,
                    follow_redirects=follow_redirects,
                )
            except httpx.HTTPError as exc:
                if query and attempt + 1 < attempts:
                    self.sleep(0.5 * (2**attempt))
                    continue
                remote_task_may_exist = remote_task_may_exist or (
                    self._unsafe_mutation(method, query) and not isinstance(exc, httpx.ConnectError)
                )
                code = (
                    ProviderErrorCode.TIMEOUT
                    if isinstance(exc, httpx.TimeoutException)
                    else ProviderErrorCode.NETWORK_ERROR
                )
                raise ProviderAPIError(
                    f'{self.provider_name} request failed: {self.redact(exc)}',
                    code=code,
                    retryable=True,
                    fallback_allowed=not remote_task_may_exist,
                    remote_task_may_exist=remote_task_may_exist,
                ) from exc

            is_transient = response.status_code == 429 or 500 <= response.status_code < 600
            if query and is_transient and attempt + 1 < attempts:
                self.sleep(0.5 * (2**attempt))
                continue
            break

        assert response is not None
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            provider_code, detail = self._response_error(response)
            error = ProviderAPIError.from_provider_response(
                f'{self.provider_name} API returned HTTP {response.status_code}: {self.redact(detail)}',
                provider_code=provider_code,
                http_status=response.status_code,
                remote_task_may_exist=remote_task_may_exist,
            )
            raise error from exc

        return response

    @staticmethod
    def _response_error(response: httpx.Response) -> tuple[Optional[str], str]:
        try:
            payload = response.json()
        except ValueError:
            return None, response.text[:500]
        if isinstance(payload, dict):
            error = payload.get('error')
            if isinstance(error, dict):
                code = error.get('code')
                return (str(code) if code is not None else None), str(error.get('message') or code or error)
            code = payload.get('code')
            return (str(code) if code is not None else None), str(payload.get('message') or code or payload)
        return None, str(payload)

    @staticmethod
    def _unsafe_mutation(method: str, query: bool) -> bool:
        return not query and method.upper() not in {'GET', 'HEAD', 'OPTIONS'}
