from typing import Optional
from urllib.parse import quote

from openapi.providers.base import BaseClient, BaseResult, Token
from openapi.exceptions import DisallowedHost
from openapi.enums import IntegerChoices


class Code(IntegerChoices):
    FAIL = -1, '失败'
    SUCCESS = 0, '成功'
    INVALID_WHITE_LIST = 40164, 'ip 未在白名单'


class Result(BaseResult):
    errcode: int = Code.SUCCESS
    errmsg: Optional[str]
    msgid: Optional[int]


class Client(BaseClient):
    NAME = '微信服务号'
    API_BASE_URL = 'https://api.weixin.qq.com/cgi-bin'
    API_VERSION = ''

    def __init__(self, app_id, secret):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        self.codes = Code

    def request(
        self, method, endpoint, params=None, data=None,
        token_request=False, is_oauth=False,
    ):
        if not token_request:
            if params is None:
                params = {}

            if 'access_token' not in params and not is_oauth:
                params['access_token'] = self.access_token

        # Support wechat oauth login
        api_base_url = self.API_BASE_URL
        if is_oauth:
            api_base_url = self.API_BASE_URL.replace('/cgi-bin', '')

        request_url = f'{api_base_url}{endpoint}'
        response = self._request(
            method, request_url,
            params=params, json=data
        )
        if response is None:
            return Result(code=self.codes.FAIL)

        result = response.json()
        if 'errcode' in result:
            return Result(**result)
        else:
            return Result(data=result)

    def check_token(self, access_token):
        result = self.request(
            'get', '/get_api_domain_ip',
            params={'access_token': access_token}
        )
        return result.code == self.codes.SUCCESS

    def fetch_access_token(self):
        result = self.request(
            'get', '/token', params={
                'grant_type': 'client_credential',
                'appid': self.app_id,
                'secret': self.secret
            },
            token_request=True
        )
        if result.errcode == self.codes.SUCCESS:
            self._token = Token(**result.data)

        if result.errcode == self.codes.INVALID_WHITE_LIST:
            raise DisallowedHost(result.errmsg)

    def get_authorize_url(
        self, scope='snsapi_base', state='',
        redirect_uri=''
    ):
        redirect_uri = quote(redirect_uri, safe='')
        url_list = [
            'https://open.weixin.qq.com',
            '/connect/oauth2/authorize?appid=',
            self.app_id,
            '&redirect_uri=',
            redirect_uri,
            '&response_type=code&scope=',
            scope
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
            'snsapi_login'  # scope
        ]
        if state:
            url_list.extend(['&state=', state])
        url_list.append('#wechat_redirect')
        return ''.join(url_list)
