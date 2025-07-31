from typing import Optional, Union, List, Dict
from pydantic import Field

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 0, '成功'


class Result(BaseResult):
    status_code: Optional[int] = Field(alias='StatusCode')


class Client(BaseClient):
    NAME = '飞书 - 群组机器人'
    API_BASE_URL = 'https://open.feishu.cn/open-apis/bot/'
    API_VERSION = 'v2'

    def __init__(self, secret=None):
        super().__init__()
        self.secret = secret
        self.codes = Code

    def fetch_access_token(self):
        pass

    def request(
        self,
        method,
        endpoint,
        json: Optional[Union[Dict, List]] = None,
    ):
        request_url = f'{self.API_BASE_URL}{self.API_VERSION}{endpoint}'
        response = self._request(method, request_url, json=json)
        return Result(**(response.json() if response else {'code': self.codes.FAIL}))
