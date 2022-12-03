from typing import Optional

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult, Token


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 200, '成功'
    INVALID_KEY = 98710201, 'APPID 或 SECRET_KEY 无效'


class Result(BaseResult):
    msg: Optional[str] = ''


class Client(BaseClient):
    NAME = '易知课堂'
    API_VERSION = ''
    API_BASE_URL = 'https://app-api.yizhiweixin.com/open-api'

    def __init__(
        self, app_id, secret,
        decrypt_key=None, decrypt_token=None
    ):
        super().__init__()
        self.codes = Code
        self.app_id = app_id
        self.secret = secret

        self.decrypt_key = decrypt_key
        self.decrypt_token = decrypt_token

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False
    ) -> Result:
        if not token_request:
            params = params or {}
            if 'access_token' not in params:
                params['access_token'] = self.access_token

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, params=params, json=data)
        return Result(**response.json()) if response else Result(code=self.codes.FAIL)

    def fetch_access_token(self):
        result = self.request(
            'get', '/accessToken', params={
                'appid': self.app_id,
                'secret_key': self.secret,
                'grant_type': 'client_credential'
            },
            token_request=True
        )
        if result.code == self.codes.SUCCESS:
            self._token = Token(**result.data)

    def decrypt(self, encrypt, timestamp, nonce, msg_signature):
        pass
