import httpx
import secrets
import hashlib
from typing import Dict
from pathlib import Path

from openapi.providers.base import BaseClient, BaseResult
from openapi.utils import xml_to_dict, dict_to_xml


class Result(BaseResult):
    return_code: str


def calculate_signature(params, api_key, sign_type='MD5'):
    if sign_type == 'MD5':
        h = hashlib.md5()
    else:
        h = hashlib.md5()

    data = [f'{k}={params[k]}' for k in sorted(params) if params[k]]
    if api_key:
        data.append('key={0}'.format(api_key))
    h.update(bytes('&'.join(data), encoding='utf-8'))
    return h.hexdigest().upper()


class Client(BaseClient):

    API_BASE_URL = 'https://api.mch.weixin.qq.com'
    API_VERSION = ''

    def __init__(
        self, app_id, mch_id, api_key_path, is_sandbox
    ):
        super().__init__()
        self.app_id = app_id
        self.mch_id = mch_id
        self.api_key_path = api_key_path
        self.is_sandbox = is_sandbox

        with open(Path(api_key_path)) as fd:
            self.api_key = fd.read().replace('\r\n', '')

    @property
    def debug_api_key(self):
        return ''

    def request(
        self, method: str, endpoint: str,
        params: Dict = None, data: Dict = None
    ):
        request_url = f'{self.API_BASE_URL}{"/sandboxnew" if self.is_sandbox else ""}{endpoint}'

        if data:
            data['app_id'] = self.app_id
            data['mch_id'] = self.mch_id

            if 'nonce_str' not in data:
                data['nonce_str'] = secrets.token_hex(16)

            data['sign'] = calculate_signature(
                data, self.debug_api_key if self.is_sandbox else self.api_key
            )

        response = httpx.request(
            method, request_url,
            params=params, data=dict_to_xml(data).encode('utf-8')
        )
        return xml_to_dict(response.content)

    def fetch_access_token(self):
        pass
