import time
import datetime
from typing import Optional
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import MD5, Hash

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult, Token


def calculate_signature(params, api_key):
    data = f'appId={params["appId"]}&timestamp={params["timestamp"]}&version={params["version"]}'
    h = Hash(algorithm=MD5(), backend=default_backend())
    h.update(f'{params["method"]}?{data}{api_key}'.encode('utf-8'))
    return h.finalize().hex()


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 0, '成功'
    INVALID_WHITE_LIST = 2051, 'ip 未在白名单'


class Result(BaseResult):
    success: bool
    error_code: Optional[int]
    error_msg: Optional[str]


class Client(BaseClient):
    NAME = '快手'
    API_VERSION = 1
    API_BASE_URL = 'https://openapi.kwaixiaodian.com'

    def __init__(self, app_id, secret):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        self.codes = Code

    def request(self, method, endpoint, action=None, params=None, data=None, token_request=False):
        if data is not None:
            public_params = {
                'appkey': self.app_id,
                'timestamp': str(int(time.time() * 1000)),
                'access_token': '',
                'version': self.API_VERSION,
                'method': action,
                'signMethod': 'HMAC_SHA256',
            }
            public_params['sign'] = calculate_signature(public_params, self.secret)
            public_params['param'] = None

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, params=params, json=data)
        return Result(**response.json())
