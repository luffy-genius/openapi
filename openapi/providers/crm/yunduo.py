import time
import typing
import hmac
import hashlib

from openapi.providers.base import BaseClient, BaseResult
from openapi.enums import IntegerChoices, TextChoices


class SignType(TextChoices):
    MD5 = 'MD5', 'MD5'
    SHA256 = 'SHA256', 'SHA256'


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 200, '操作成功'
    REPEATED = 600, '重复的数据'


class Result(BaseResult):
    msg: typing.Optional[str] = ''


def calc_signature(
    params: typing.Dict, company_id: str,
    sign_key: str, timestamp: int, sign_type: SignType
):
    if sign_type == SignType.SHA256:
        return hmac.new(f'{timestamp}{company_id}'.encode(), sign_key.encode(), digestmod=hashlib.sha256).hexdigest()

    if sign_type == SignType.MD5:
        sorted_params = [f'{key}={params[key]}' for key in sorted(params) if params[key]]
        sign_string = f'{"&".join(sorted_params)}{sign_key}{timestamp}'
        h = hashlib.md5()
        h.update(sign_string.encode())
        return h.hexdigest()


class Client(BaseClient):
    NAME = '云朵'
    API_BASE_URL = 'https://outcrmapi.yunduocrm.com'
    API_VERSION = ''

    def __init__(self, company_id):
        super().__init__()

        self.company_id = company_id
        self.codes = Code

    def fetch_access_token(self):
        pass

    def request(
        self, method, endpoint, sign_key, sign_type: SignType,
        params: typing.Dict = None,
        data: typing.Dict = None,
        json: typing.Dict = None
    ):
        request_url = f'{self.API_BASE_URL}{endpoint}'
        timestamp = int(time.time())
        default_headers = {'timestamp': f'{timestamp}'}
        if sign_type == SignType.MD5:
            default_headers.update(
                token=sign_key,
                sign=calc_signature(
                    json, self.company_id, sign_key,
                    timestamp, sign_type
                )
            )
        else:
            default_headers.update(
                accessToken=sign_key,
                signature=calc_signature(
                    json, self.company_id, sign_key,
                    timestamp, sign_type
                )
            )
        response = self._request(
            method, request_url, params, data, json,
            headers=default_headers
        )
        return Result(**(response.json() if response else {'code': self.codes.FAIL}))
