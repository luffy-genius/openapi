import httpx

from .base import BaseClient


class Client(BaseClient):
    API_BASE_URL = 'https://openapi-fxg.jinritemai.com/'
    API_VERSION = 2

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False
    ):
        if token_request:
            params['access_token'] = self.access_token

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = httpx.request(
            method, request_url,
            params=params, data=data
        )
        return response.json()

    def fetch_access_token(self):
        response = self.request(
            'post', '/token/create',
        )
