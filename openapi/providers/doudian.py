import json

from typing import Optional, Dict
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import SHA256, MD5, Hash
from cryptography.hazmat.primitives.hmac import HMAC

from datetime import datetime

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult, Token


SIGN_FIELDS = [
    'app_key', 'method', 'param_json', 'timestamp', 'v'
]


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 10000, '成功'


def format_params(params, secret=None):
    data = [
        '{0}{1}'.format(k, params[k])
        for k in params if k in SIGN_FIELDS
    ]
    return f"{secret}{''.join(sorted(data))}{secret}"


def calc_signature(params, secret):
    pattern = format_params(params, secret).encode('utf-8')
    hmac = HMAC(key=secret.encode('utf-8'), algorithm=SHA256(), backend=default_backend())
    hmac.update(pattern)
    signature = hmac.finalize()
    return signature.hex()


class Result(BaseResult):
    log_id: Optional[str]
    msg: Optional[str]
    sub_code: Optional[str]
    sub_msg: Optional[str]


class Client(BaseClient):
    NAME = '抖店'
    API_BASE_URL = 'https://openapi-fxg.jinritemai.com/'
    API_VERSION = 2

    def __init__(self, app_id, secret, shop_id):
        super().__init__()

        self.app_id = app_id
        self.secret = secret
        self.shop_id = shop_id
        self.codes = Code

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False
    ) -> Result:
        if params is None:
            params = {
                'v': self.API_VERSION,
                'app_key': self.app_id,
                'timestamp': datetime.now().strftime('%Y-%m-%d %X'),
                'method': '.'.join(filter(lambda _: bool(_), endpoint.split('/'))),
                'param_json': json.dumps(
                    {
                        key: value
                        for key, value in data.items() if value is not None
                    },
                    sort_keys=True, separators=(',', ':')
                )
            }
        sign = calc_signature(params, self.secret)
        params['sign_method'] = 'hmac-sha256'
        params['sign'] = sign
        if not token_request:
            params['access_token'] = self.access_token

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, params=params, data=data)
        return Result(**response.json()) if response else Result(code=self.codes.FAIL)

    def fetch_access_token(self):
        result = self.request(
            'post', '/token/create', data={
                'code': '',
                'grant_type': 'authorization_self',
                'shop_id': self.shop_id
            },
            token_request=True
        )
        if result.code == self.codes.SUCCESS:
            self._token = Token(**result.data)

    def refresh_access_token(self):
        result = self.request(
            'post', '/token/create', data={
                'refresh_token': self._token.refresh_token,
                'grant_type': 'refresh_token',
            }
        )
        if result.code == self.codes.SUCCESS:
            self._token = Token(**result.data)

    def callback(self, app_id: str, sign: str, body: bytes) -> Optional[Dict]:
        data = body.decode('utf-8')
        if not data:
            return

        if app_id != self.app_id:
            return

        h = Hash(algorithm=MD5(), backend=default_backend())
        h.update(f'{app_id}{data}{self.secret}'.encode('utf-8'))
        if h.finalize().hex() != sign:
            return

        return json.loads(data)
