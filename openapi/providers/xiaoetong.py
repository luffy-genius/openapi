#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2022/7/1

import json
import httpx

from .base import BaseClient, BaseResult, Token


SUCCESS_CODE = 0


class Result(BaseResult):
    pass


class Client(BaseClient):

    API_VERSION = ''
    API_BASE_URL = 'https://api.xiaoe-tech.com'

    def __init__(self, app_id, secret, client_id=None):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        self.client_id = client_id

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False
    ) -> Result:
        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = httpx.request(
            method, request_url,
            params=params,
            data=json.dumps(data).encode() if data is not None else None
        )

    def fetch_access_token(self):
        result = self.request(
            'post', '/token', params={
                'app_id': self.app_id,
                'secret_key': self.secret,
                'client_id': self.client_id,
                'grant_type': 'client_credential'
            },
            token_request=True
        )
        if result.code == SUCCESS_CODE:
            self._token = Token(**result.data)
