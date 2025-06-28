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
    h.update(f'{params["method"]}?{data}{api_key}'.encode())
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
    NAME = '小红书'
    API_VERSION = '2.0'
    API_BASE_URL = 'https://ark.xiaohongshu.com'

    def __init__(self, app_id, secret, user_id, seller_id, redirect_url=''):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        self.user_id = user_id
        self.seller_id = seller_id
        self.redirect_url = redirect_url
        self.codes = Code

    def request(self, method, endpoint, action=None, params=None, data=None, token_request=False, headers=None):
        if data is not None:
            public_params = {
                'appId': self.app_id,
                'version': self.API_VERSION,
                'timestamp': str(int(time.time() * 1000)),
                'method': action,
            }
            public_params['sign'] = calculate_signature(public_params, self.secret)
            data.update(**public_params)
            if 'accessToken' not in data and not token_request:
                data['accessToken'] = self.access_token

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, params=params, json=data, headers=headers)
        return Result(**response.json())

    def check_token(self, access_token=None):
        return self._token.is_valid

    def fetch_access_token(self):
        code_result = self.request(
            'get',
            '/api/edith/openapi/getcode',
            params={
                'appId': self.app_id,
                'userId': self.user_id,
                'sellerId': self.seller_id,
                'subsystemAlias': 'ark',
                'redirectUrl': self.redirect_url,
            },
        )
        code = None
        if code_result.code == Code.SUCCESS and code_result.success:
            code = code_result.data['code']

        if code is None:
            return

        result = self.request(
            'post',
            '/ark/open_api/v3/common_controller',
            action='oauth.getAccessToken',
            data={'code': code},
            token_request=True,
        )
        if result.error_code == Code.SUCCESS and result.success:
            self._token = Token(
                access_token=result.data['accessToken'],
                refresh_token=result.data['refreshToken'],
                expires_in=result.data['accessTokenExpiresAt'] / 1000 - time.time(),
                expires_at=datetime.datetime.fromtimestamp(result.data['accessTokenExpiresAt'] / 1000),
            )

    def refresh_access_token(self):
        result = self.request(
            'post',
            '/ark/open_api/v3/common_controller',
            action='oauth.refreshToken',
            data={'refreshToken': self._token.refresh_token},
            token_request=True,
        )
        if result.error_code == Code.SUCCESS and result.success:
            self._token = Token(
                access_token=result.data['accessToken'],
                refresh_token=result.data['refreshToken'],
                expires_in=result.data['accessTokenExpiresAt'] / 1000 - time.time(),
                expires_at=datetime.datetime.fromtimestamp(result.data['accessTokenExpiresAt'] / 1000),
            )
