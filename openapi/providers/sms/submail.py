import typing

from openapi.providers.base import BaseClient, BaseResult
from openapi.enums import TextChoices


class Code(TextChoices):
    FAIL = 'error', '失败'
    SUCCESS = 'success', '成功'


class Result(BaseResult):
    status: Code
    send_id: typing.Optional[str]
    fee: typing.Optional[int]
    sms_credits: typing.Optional[int]
    msg: typing.Optional[str]


class Client(BaseClient):
    NAME = '赛邮-云通信'
    API_BASE_URL = 'https://api.mysubmail.com'
    API_VERSION = ''

    def __init__(self, app_id, app_key):
        super(Client, self).__init__()
        self.app_id = app_id
        self.app_key = app_key

        self.codes = Code

    def fetch_access_token(self):
        pass

    def request(
        self, method, endpoint,
        params: typing.Dict = None,
        data: typing.Dict = None,
        json: typing.Dict = None,
    ):
        request_url = f'{self.API_BASE_URL}{endpoint}'
        json.update(**{
            'appid': self.app_id, 'signature': self.app_key
        })
        response = self._request(method, request_url, params, data, json)
        return Result(**(response.json() if response else {'status': self.codes.FAIL}))
