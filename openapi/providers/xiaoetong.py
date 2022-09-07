from typing import Optional

from openapi.exceptions import DisallowedHost

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult, Token


class Code(IntegerChoices):
    SUCCESS = 0, '成功'
    INVALID_WHITE_LIST = 2051, 'ip 未在白名单'


class Result(BaseResult):
    msg: Optional[str] = ''


class Client(BaseClient):
    NAME = '小鹅通'
    API_VERSION = ''
    API_BASE_URL = 'https://api.xiaoe-tech.com'

    def __init__(self, app_id, secret, client_id=None):
        super().__init__()
        self.codes = Code

        self.app_id = app_id
        self.secret = secret
        self.client_id = client_id

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False
    ) -> Result:
        if not token_request:
            if method == 'get':
                params['access_token'] = self.access_token

            if method == 'post':
                data['access_token'] = self.access_token
        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(
            method, request_url,
            params=params, json=data
        )
        return Result(**response.json())

    def fetch_access_token(self):
        result: Result = self.request(
            'get', '/token', params={
                'app_id': self.app_id,
                'secret_key': self.secret,
                'client_id': self.client_id,
                'grant_type': 'client_credential'
            },
            token_request=True
        )
        if result.code == self.codes.SUCCESS:
            self._token = Token(**result.data)

        if result.code == self.codes.INVALID_WHITE_LIST:
            raise DisallowedHost(result.msg)
