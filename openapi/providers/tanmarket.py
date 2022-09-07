import time
import typing
import hashlib

from openapi.providers.base import BaseClient


def calc_signature(string: str):
    return hashlib.sha256(string.encode('utf-8')).hexdigest()


class Client(BaseClient):
    NAME = '探马'
    API_BASE_URL = 'https://api.tanmarket.cn:20066/api/'
    API_VERSION = 'v3'

    def __init__(self, app_id, app_key):
        super().__init__()
        self.app_id = app_id
        self.app_key = app_key

    def fetch_access_token(self):
        pass

    def request(
        self, method, endpoint,
        params: typing.Dict = None,
        data: typing.Dict = None,
        json: typing.Dict = None,
        headers: typing.Dict = None
    ):
        request_url = f'{self.API_BASE_URL}{self.API_VERSION}{endpoint}'
        if headers is None:
            headers = {}

        timestamp = f'{int(time.time() * 1000)}'
        headers.update(**{
            'appId': self.app_id,
            'timestamp': timestamp,
            'sign': calc_signature(f'{self.app_id}{timestamp}{data or json}{self.app_key}'.replace("'", '"'))
        })
        return self._request(method, request_url, params, data, json, headers)
