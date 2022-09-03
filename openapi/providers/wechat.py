import json
import httpx
from typing import Optional

from openapi.providers.base import BaseClient, BaseResult, Token
from openapi.exceptions import DisallowedHost

SUCCESS_CODE = 0
INVALID_WHITE_LIST_CODE = 40164


class Result(BaseResult):
    errcode: int = SUCCESS_CODE
    errmsg: Optional[str]
    msgid: Optional[int]


class Client(BaseClient):

    API_BASE_URL = 'https://api.weixin.qq.com/cgi-bin'
    API_VERSION = ''

    def __init__(self, app_id, secret):
        super().__init__()
        self.app_id = app_id
        self.secret = secret

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False
    ):
        if not token_request:
            if params is None:
                params = {}
            params['access_token'] = self.access_token

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = httpx.request(
            method, request_url,
            params=params, data=json.dumps(data).encode() if data else None
        )
        return Result(**({'data': response.json()} if token_request else response.json()))

    def fetch_access_token(self):
        result = self.request(
            'get', '/token', params={
                'grant_type': 'client_credential',
                'appid': self.app_id,
                'secret': self.secret
            },
            token_request=True
        )
        if result.errcode == SUCCESS_CODE:
            self._token = Token(**result.data)

        if result.errcode == INVALID_WHITE_LIST_CODE:
            raise DisallowedHost(result.errmsg)
