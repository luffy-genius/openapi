#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Date: 2022/7/1

import json
import httpx
from typing import Optional

from openapi.exceptions import DisallowedHost

from .base import BaseClient, BaseResult, Token


SUCCESS_CODE = 0
INVALID_WHITE_LIST_CODE = 2051


class Result(BaseResult):
    msg: Optional[str] = ''


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
        if not token_request:
            if method == 'get':
                params['access_token'] = self.access_token

            if method == 'post':
                data['access_token'] = self.access_token

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = httpx.request(
            method, request_url,
            params=params,
            data=json.dumps(
                data, ensure_ascii=False
            ).encode() if data is not None else None
        )
        return Result(**response.json())

    def fetch_access_token(self):
        result: Result = self.request(
            'get', '/token', params={
                'app_id': self.app_id,
                'secret_key': self.secret,
                'client_id': self.client_id,
                'grant_type': 'client_credential'
            },
            token_request=True
        )
        if result.code == SUCCESS_CODE:
            self._token = Token(**result.data)

        if result.code == INVALID_WHITE_LIST_CODE:
            raise DisallowedHost(result.msg)
