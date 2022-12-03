import time
import uuid
import hmac
import base64
import inflection
from typing import Optional, Union
from urllib.parse import quote

from openapi.enums import TextChoices
from openapi.providers.base import BaseClient, BaseResult


class Code(TextChoices):
    SUCCESS = 'OK', '成功'
    FAIL = 'FAIL', '失败'


class Result(BaseResult):
    request_id: str
    biz_id: Optional[str]
    code: Union[Code, str] = Code.SUCCESS


class Client(BaseClient):
    NAME = '阿里云'
    VERSION = ''
    API_BASE_URL = 'http://{}.aliyuncs.com'

    def __init__(self, app_id, secret):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        self.codes = Code

    def request(
        self, method, prefix, action, version,
        params=None, data=None
    ):
        public_params = {
            'Action': action,
            'Version': version,
            'Timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'SignatureMethod': 'HMAC-SHA1',
            'SignatureVersion': '1.0',
            'SignatureNonce': uuid.uuid4().hex,
            'AccessKeyId': self.app_id,
            'Format': 'JSON',
        }
        if method == 'get':
            params.update(**public_params)
        else:
            data.update(**public_params)

        sorted_data = sorted((params if method == 'get' else data).items(), key=lambda item: item[0])
        sign_string = ''
        for k, v in sorted_data:
            if not v:
                continue
            sign_string += quote(k, safe='~') + "=" + quote(v, safe='~') + '&'

        secret = '{}&'.format(self.secret)
        hmb = hmac.new(
            secret.encode(),
            ('GET&%2F&' + quote(sign_string[:-1], safe='~')).encode(), 'sha1'
        ).digest()
        signature = quote(base64.standard_b64encode(hmb).decode('ascii'), safe='~')
        query_string = f'{sign_string[:-1]}&Signature={signature}'
        request_url = f'{self.API_BASE_URL.format(prefix)}?{query_string}'
        response = self._request(method, request_url)
        if not response:
            return Result(code=self.codes.FAIL)

        result = {inflection.underscore(k): v for k, v in response.json().items()}
        return Result(**result, data=result)

    def fetch_access_token(self):
        pass
