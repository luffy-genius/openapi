from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, Optional

import httpx

from openapi.providers.media_generation.exceptions import ProviderAPIError


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
    ) -> Dict[str, Any]:
        attempts = self.max_query_retries + 1 if query else 1
        response = None
        for attempt in range(attempts):
            try:
                response = self.http_client.request(method, url, headers=headers, params=params, json=json_body)
            except httpx.HTTPError as exc:
                if query and attempt + 1 < attempts:
                    self.sleep(0.5 * (2**attempt))
                    continue
                raise ProviderAPIError(f'{self.provider_name} request failed: {self.redact(exc)}') from exc

            is_transient = response.status_code == 429 or 500 <= response.status_code < 600
            if query and is_transient and attempt + 1 < attempts:
                self.sleep(0.5 * (2**attempt))
                continue
            break

        assert response is not None
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._response_error(response)
            raise ProviderAPIError(
                f'{self.provider_name} API returned HTTP {response.status_code}: {self.redact(detail)}'
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderAPIError(f'{self.provider_name} API returned invalid JSON') from exc
        if not isinstance(payload, dict):
            raise ProviderAPIError(f'{self.provider_name} API returned an invalid response object')
        if capture_response_headers:
            payload['_response_headers'] = {
                key: value
                for key, value in response.headers.items()
                if key.lower() in {'x-tt-logid', 'x-request-id', 'request-id'}
            }
        return payload

    @staticmethod
    def _response_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text[:500]
        if isinstance(payload, dict):
            error = payload.get('error')
            if isinstance(error, dict):
                return str(error.get('message') or error.get('code') or error)
            return str(payload.get('message') or payload.get('code') or payload)
        return str(payload)
