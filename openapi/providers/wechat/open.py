import base64
import hashlib
import json
import socket
import struct
from typing import Optional
from urllib.parse import quote

from Crypto.Cipher import AES

from openapi.enums import IntegerChoices
from openapi.exceptions import DisallowedHost, OpenAPIException
from openapi.providers.base import BaseClient, BaseResult, Token


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 0, '成功'
    INVALID_WHITE_LIST = 40164, 'ip 未在白名单'


class Result(BaseResult):
    errcode: int = Code.SUCCESS
    errmsg: Optional[str]
    msgid: Optional[int]


class Client(BaseClient):
    NAME = '微信服务号/视频号'
    API_BASE_URL = 'https://api.weixin.qq.com/cgi-bin'
    API_VERSION = ''

    def __init__(self, app_id, secret, decrypt_key=None, decrypt_token=None):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        self.codes = Code

        self.decrypt_key = decrypt_key
        self.decrypt_token = decrypt_token

    def request(
        self,
        method,
        endpoint,
        params=None,
        data=None,
        token_request=False,
        is_oauth=True,
        replace_url=True,
        result_processor=None,
    ):
        if not token_request:
            if params is None:
                params = {}

            if 'access_token' not in params and not is_oauth:
                params['access_token'] = self.access_token

        # Support wechat oauth login
        api_base_url = self.API_BASE_URL
        if not is_oauth and replace_url:
            api_base_url = self.API_BASE_URL.replace('/cgi-bin', '')

        request_url = f'{api_base_url}{endpoint}'
        response = self._request(method, request_url, params=params, json=data)
        if response is None:
            return Result(code=self.codes.FAIL)

        result = response.json()
        if 'errcode' in result:
            return Result(**result) if result_processor is None else result_processor(**result)
        else:
            return Result(data=result)

    def check_token(self, access_token):
        result = self.request('get', '/get_api_domain_ip', params={'access_token': access_token})
        return result.code == self.codes.SUCCESS

    def fetch_access_token(self):
        result = self.request(
            'get',
            '/token',
            params={'grant_type': 'client_credential', 'appid': self.app_id, 'secret': self.secret},
            token_request=True,
        )
        if result.errcode == self.codes.SUCCESS:
            self._token = Token(**result.data)
        else:
            if result.errcode == self.codes.INVALID_WHITE_LIST:
                raise DisallowedHost(result.errmsg)
            else:
                raise OpenAPIException(result.code, result.errmsg)

    def get_authorize_url(self, scope='snsapi_base', state='', redirect_uri=''):
        redirect_uri = quote(redirect_uri, safe='')
        url_list = [
            'https://open.weixin.qq.com',
            '/connect/oauth2/authorize?appid=',
            self.app_id,
            '&redirect_uri=',
            redirect_uri,
            '&response_type=code&scope=',
            scope,
        ]
        if state:
            url_list.extend(['&state=', state])
        url_list.append('#wechat_redirect')
        return ''.join(url_list)

    def get_qrcode_url(self, state='', redirect_uri=''):
        redirect_uri = quote(redirect_uri, safe='')
        url_list = [
            'https://open.weixin.qq.com',
            '/connect/qrconnect?appid=',
            self.app_id,
            '&redirect_uri=',
            redirect_uri,
            '&response_type=code&scope=',
            'snsapi_login',  # scope
        ]
        if state:
            url_list.extend(['&state=', state])
        url_list.append('#wechat_redirect')
        return ''.join(url_list)

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
        length = socket.ntohl((struct.unpack('I', content[:4]))[0])
        content = content[4 : length + 4]
        try:
            data = json.loads(content.decode())
            return Result(code=self.codes.SUCCESS, message='OK', data=data)
        except Exception as exc:
            return Result(code=self.codes.FAIL, message=str(exc))
