import base64
import hashlib
import socket
import struct
from typing import Optional
from Crypto.Cipher import AES

from openapi.exceptions import DisallowedHost

from openapi.enums import IntegerChoices
from openapi.providers.base import BaseClient, BaseResult, Token
from openapi.utils import xml_to_dict


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 0, '成功'
    INVALID_WHITE_LIST = 2051, 'ip 未在白名单'


class Result(BaseResult):
    msg: Optional[str] = ''


class Client(BaseClient):
    NAME = '小鹅通'
    API_VERSION = ''
    API_BASE_URL = 'https://api.xiaoe-tech.com'

    def __init__(
        self, app_id, secret,
        client_id=None,
        decrypt_key=None, decrypt_token=None
    ):
        super().__init__()
        self.codes = Code

        self.app_id = app_id
        self.secret = secret
        self.client_id = client_id

        self.decrypt_key = decrypt_key
        self.decrypt_token = decrypt_token

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False
    ) -> Result:
        if not token_request:
            if method == 'get' and params and 'access_token' not in params:
                params['access_token'] = self.access_token

            if method == 'post' and data and 'access_token' not in data:
                data['access_token'] = self.access_token

        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, params=params, json=data)
        return Result(**response.json()) if response else Result(code=self.codes.FAIL)

    def check_token(self, access_token):
        result = self.request(
            'post', '/xe.user.batch.get/1.0.0',
            data={'access_token': access_token, 'page': 1, 'page_size': 1}
        )
        return result.code == self.codes.SUCCESS

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
        if result.code == self.codes.SUCCESS:
            self._token = Token(**result.data)

        if result.code == self.codes.INVALID_WHITE_LIST:
            raise DisallowedHost(result.msg)

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
        xml_length = socket.ntohl((struct.unpack('I', content[:4]))[0])
        xml_content = content[4:xml_length + 4]
        return Result(
            code=self.codes.SUCCESS, msg='OK',
            data=xml_to_dict(f'<xml>{xml_content.decode()}</xml>')
        )
