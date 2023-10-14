import uuid
import typing
import datetime

from openapi.providers.base import BaseClient, BaseResult
from openapi.enums import IntegerChoices
from openapi.utils import xml_to_dict


class Code(IntegerChoices):
    SUCCESS = 0, '成功'
    FAIL = -1, '失败'


class Result(BaseResult):
    error: int
    message: typing.Optional[str]


class Client(BaseClient):
    NAME = '中网信'
    API_BASE_URL = 'http://139.224.36.226:382'
    API_VERSION = ''

    def __init__(self, app_id, app_key):
        super(Client, self).__init__()
        self.app_id = app_id
        self.app_key = app_key

        self.codes = Code

    def request(
        self, method, endpoint,
        params: typing.Dict = None, data: typing.Dict = None
    ):
        default_data = {
            'apName': self.app_id, 'apPassword': self.app_key,
            'sendTime': datetime.datetime.now().strftime('%Y%m%d%H%M%S'),
            'serviceId': {
                'orgMsgId': uuid.uuid4().hex
            }, 'srcId': '123'
        }
        default_data.update(**data)
        request_url = f'{self.API_BASE_URL}{endpoint}'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = self._request(method, request_url, params, default_data, headers=headers)
        return Result(**(xml_to_dict(response.content) if response else {'status': self.codes.FAIL}))
