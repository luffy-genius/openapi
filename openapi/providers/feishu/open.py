import typing

from openapi.providers.base import BaseClient, BaseResult, Token
from openapi.enums import IntegerChoices


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 0, '成功'


class Result(BaseResult):
    msg: typing.Optional[str]


class Client(BaseClient):
    NAME = '飞书 - 开发平台'
    API_BASE_URL = 'https://open.feishu.cn/open-apis'
    API_VERSION = 'v3'

    def __init__(self, app_id, secret, version=API_VERSION):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        self.version = version

        self.codes = Code

    def fetch_access_token(self):
        result = self.request(
            'post', '/auth/v3/tenant_access_token/internal',
            json={
                'app_id': self.app_id,
                'app_secret': self.secret
            },
            token_request=True
        )
        if result.code == self.codes.SUCCESS:
            self._token = Token(
                access_token=result.data['tenant_access_token'],
                expires_in=result.data['expire']
            )

    def request(
        self, method, endpoint,
        json: typing.Union[typing.Dict, typing.List] = None,
        headers: typing.Optional[typing.Dict] = None,
        token_request=False
    ):
        request_url = f'{self.API_BASE_URL}{endpoint}'
        if not token_request:
            if headers is None:
                headers = {}

            headers['Authorization'] = f'Bearer {self.access_token}'

        response = self._request(method, request_url, headers=headers, json=json)
        if token_request:
            result = response.json()
            return Result(code=result['code'], msg=result['msg'], data=result)
        return Result(**response.json())
