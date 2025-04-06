import hashlib
import time
import typing

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult
from openapi.utils import encode_json


def calc_signature(string: str):
    return hashlib.sha256(string.encode('utf-8')).hexdigest()


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 0, '成功'
    INVALID_SIGN = 1002, '签名校验未通过'
    INVALID_TIMESTAMP = 1003, '请求时间与服务器时间相差过大，请校对时间后重新请求'
    REPEATED_MOBILE = 40417, '请求参数验证失败：电话号码重复'


class Result(BaseResult):
    pass


class Client(BaseClient):
    NAME = '探马'
    API_BASE_URL = 'https://api.tanmarket.cn:20066/api'
    API_VERSION = ''

    def __init__(self, app_id, app_key):
        super().__init__()
        self.app_id = app_id
        self.app_key = app_key

        self.codes = Code

    def fetch_access_token(self):
        pass

    def request(
        self,
        method,
        endpoint,
        params: typing.Dict = None,
        data: typing.Union[typing.Dict, typing.List] = None,
        json: typing.Union[typing.Dict, typing.List] = None,
        headers: typing.Dict = None,
    ):
        request_url = f'{self.API_BASE_URL}{self.API_VERSION}{endpoint}'
        if headers is None:
            headers = {}

        timestamp = f'{int(time.time() * 1000)}'
        string = f'{self.app_id}{timestamp}{encode_json(data or json)}{self.app_key}'
        headers.update(**{'appId': self.app_id, 'timestamp': timestamp, 'sign': calc_signature(string)})
        response = self._request(method, request_url, params, data, json, headers)
        return Result(**(response.json() if response else {'code': self.codes.FAIL}))
