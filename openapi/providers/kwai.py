import json
import time
import hmac
import hashlib
import base64
from typing import Optional
from Crypto.Cipher import AES

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult, Token


def calculate_signature(params, secret):
    sign_params = {
        key: params[key]
        for key in sorted(['access_token',  'appkey', 'method', 'param', 'signMethod', 'timestamp', 'version'])
        if params.get(key)
    }
    sign_params['signSecret'] = secret
    return base64.b64encode(hmac.new(
        secret.encode(),
        '&'.join(f'{k}={v}' for k, v in sign_params.items()).encode(),
        hashlib.sha256
    ).digest()).decode()


class Code(IntegerChoices):
    SUCCESS = 1, '成功'


class Result(BaseResult):
    result: Optional[int]
    error: Optional[str]
    error_msg: Optional[str]


class Client(BaseClient):
    NAME = '快手'
    API_VERSION = 1
    API_BASE_URL = 'https://openapi.kwaixiaodian.com'

    def __init__(self, app_id, secret, sign_secret, message_key):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        self.sign_secret = sign_secret
        self.message_key = message_key
        self.codes = Code
        self._token = Optional[Token]

    def request(self, method, endpoint, action=None, params=None, data=None, token_request=False):
        public_params = {}
        if (params is not None or data is not None) and token_request is False:
            public_params.update(**{
                'appkey': self.app_id, 'timestamp': str(int(time.time() * 1000)),
                'version': self.API_VERSION, 'method': action, 'signMethod': 'HMAC_SHA256'
            })
            public_params['access_token'] = self._token.access_token
            public_params['param'] = json.dumps(params or data)
            public_params['sign'] = calculate_signature(public_params, self.sign_secret)

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, params=public_params, json=data)
        print(response.status_code, response.json())
        return Result(**response.json())

    def decrypt(self, message):
        block = AES.new(
            base64.b64decode(self.message_key),
            AES.MODE_CBC, iv=bytes(AES.block_size)
        )
        decrypt_data = block.decrypt(base64.b64decode(message))
        length = len(decrypt_data)
        return decrypt_data[:length - int(decrypt_data[length - 1])].decode()
