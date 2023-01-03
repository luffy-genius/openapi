import json as _json
import httpx
from datetime import datetime
from typing import Optional, Union, List, Dict

from pydantic import BaseModel, Field


MESSAGE_TEMPLATE = """date: {date}
method: {method}
request-url: {endpoint}
headers: 
{headers}
params: 
{params}
data:
{data}
result:
{result}
is_error: {is_error}
errmsg: {errmsg}
"""

SENSITIVE_KEYS = ['app_key', 'secret', 'secret_key', 'signature']


def mask_sensitive_data(data):
    if type(data) != dict:
        return data

    for key, value in data.items():
        if key in SENSITIVE_KEYS:
            data[key] = "***FILTERED***"

        if type(value) == dict:
            data[key] = mask_sensitive_data(data[key])

        if type(value) == list:
            data[key] = [mask_sensitive_data(item) for item in data[key]]

    return data


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str]
    expires_in: int = 7200
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def is_valid(self):
        return (datetime.now() - self.created_at).total_seconds() < (self.expires_in - self.expires_in * 0.3)


class BaseResult(BaseModel):
    code: Optional[int]
    data: Optional[Union[List, Dict, int]]
    message: Optional[str]


class BaseClient:
    NAME = 'Unknown Client'
    API_BASE_URL = ''
    API_VERSION = ''

    def __init__(self):
        self._ignore_endpoints = []
        self._token: Optional[Token] = None
        self.enable_webhook = False
        self.webhook_url = None

    def _request(
        self, method, request_url,
        params=None, data=None, json=None, headers=None
    ) -> httpx.Response:
        response = None
        is_error = False
        errmsg = ''
        try:
            response = httpx.request(
                method, request_url, headers=headers,
                params=params, data=data, json=json
            )
            is_error = response.is_error
        except httpx.HTTPError as exc:
            is_error = True
            errmsg = str(exc)
        finally:
            _data = data or json or {}
            format_data = {
                'date': datetime.now().strftime('%Y-%m-%d %X'),
                'method': method, 'endpoint': request_url,
                'headers': _json.dumps(
                    mask_sensitive_data(headers or {}), indent=2, ensure_ascii=False
                ),
                'params': _json.dumps(
                    mask_sensitive_data(params or {}), indent=2, ensure_ascii=False
                ),
                'data': _json.dumps(
                    mask_sensitive_data(_data),
                    indent=2, ensure_ascii=False
                ) if isinstance(_data, dict) else _data,
                'result': response.text,
                'is_error': is_error, 'errmsg': errmsg
            }
            endpoint = request_url.replace(self.API_BASE_URL, '')
            if self.enable_webhook and self.webhook_url and endpoint not in self._ignore_endpoints:
                self.send_webhook_message(MESSAGE_TEMPLATE.format(**format_data))

        return response

    def fetch_access_token(self):
        raise NotImplementedError()

    def request(self, *args, **kwargs):
        raise NotImplementedError()

    def send_webhook_message(self, message):
        try:
            httpx.request('post', self.webhook_url, json={
                'msg_type': 'post', 'content': {
                    'post': {
                        'zh_cn': {
                            'title': self.NAME,
                            'content': [
                                [{'tag': 'text', 'text': message}],
                            ]
                        }
                    }
                }
            })
        except httpx.HTTPError:
            pass

    def check_token(self, access_token):
        return True

    def refresh_access_token(self):
        pass

    @property
    def access_token(self):
        if not (
            self._token and self._token.is_valid
            and self.check_token(self._token.access_token)
        ):
            self.fetch_access_token()

        return self._token.access_token

    def add_webhook(self, webhook_url, ignore_endpoints: Optional[List] = None):
        self.enable_webhook = True
        self.webhook_url = webhook_url
        if ignore_endpoints:
            self._ignore_endpoints = ignore_endpoints
