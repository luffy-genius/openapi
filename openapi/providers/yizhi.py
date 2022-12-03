import base64
import hashlib
import json
import socket
import struct
from typing import Optional
from Crypto.Cipher import AES

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult, Token


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 200, '成功'
    INVALID_KEY = 98710201, 'APPID 或 SECRET_KEY 无效'


class Result(BaseResult):
    msg: Optional[str] = ''


class Client(BaseClient):
    NAME = '易知课堂'
    API_VERSION = ''
    API_BASE_URL = 'https://app-api.yizhiweixin.com/open-api'

    def __init__(
        self, app_id, secret,
        decrypt_key=None, decrypt_token=None
    ):
        super().__init__()
        self.codes = Code
        self.app_id = app_id
        self.secret = secret

        self.decrypt_key = decrypt_key
        self.decrypt_token = decrypt_token

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False
    ) -> Result:
        if not token_request:
            params = params or {}
            if 'access_token' not in params:
                params['access_token'] = self.access_token

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, params=params, json=data)
        return Result(**response.json()) if response else Result(code=self.codes.FAIL)

    def fetch_access_token(self):
        result = self.request(
            'get', '/accessToken', params={
                'appid': self.app_id,
                'secret_key': self.secret,
                'grant_type': 'client_credential'
            },
            token_request=True
        )
        if result.code == self.codes.SUCCESS:
            self._token = Token(**result.data)

    def decrypt(self, encrypt, timestamp, nonce, signature):
        data = [self.decrypt_token, timestamp, nonce, encrypt]
        data.sort()

        sign_aligo = hashlib.sha1()
        sign_aligo.update(''.join(data).encode())
        if signature != sign_aligo.hexdigest():
            return Result(code=self.codes.FAIL, msg='签名不一致')

        key = base64.b64decode(f'{self.decrypt_key}=')
        crypter = AES.new(key, AES.MODE_CBC, key[:16])

        plain_text = crypter.decrypt(base64.b64decode(encrypt))
        pad = ord(plain_text[-1:])
        content = plain_text[16:-pad]
        json_length = socket.ntohl((struct.unpack('I', content[:4]))[0])
        json_content = content[4:json_length + 4]
        return Result(
            code=self.codes.SUCCESS, msg='OK',
            data=json.loads(json_content.decode())
        )
