import secrets
import hashlib
import time
import typing
from typing import Dict, Optional
from pathlib import Path

from openapi.enums import TextChoices
from openapi.providers.base import BaseClient, BaseResult
from openapi.utils import xml_to_dict, dict_to_xml


class Code(TextChoices):
    SUCCESS = 'SUCCESS', '成功'
    FAIL = 'FAIL', '失败'


class Result(BaseResult):
    return_code: str
    return_msg: str
    result_code: Optional[str]
    data: Optional[Dict]


def calculate_signature(params, api_key, sign_type='MD5'):
    if sign_type == 'MD5':
        h = hashlib.md5()
    else:
        h = hashlib.md5()

    data = [f'{k}={params[k]}' for k in sorted(params) if params[k]]
    if api_key:
        data.append('key={0}'.format(api_key))
    h.update(bytes('&'.join(data), encoding='utf-8'))
    return h.hexdigest().upper()


class Client(BaseClient):
    NAME = '微信支付'
    API_BASE_URL = 'https://api.mch.weixin.qq.com'
    API_VERSION = ''

    def __init__(
        self, app_id, mch_id, api_key_path, is_sandbox
    ):
        super().__init__()
        self.app_id = app_id
        self.mch_id = mch_id
        self.api_key_path = api_key_path
        self.is_sandbox = is_sandbox

        self.codes = Code

        with open(Path(api_key_path)) as fd:
            self.api_key = fd.read().replace('\r\n', '')

    @property
    def debug_api_key(self):
        return ''

    def request(
        self, method: str, endpoint: str,
        params: Dict = None, data: Dict = None
    ):
        request_url = f'{self.API_BASE_URL}{"/sandboxnew" if self.is_sandbox else ""}{endpoint}'

        if data:
            data['appid'] = self.app_id
            data['mch_id'] = self.mch_id

            if 'nonce_str' not in data:
                data['nonce_str'] = secrets.token_hex(16)

            data['sign'] = calculate_signature(
                data, self.debug_api_key if self.is_sandbox else self.api_key
            )

        response = self._request(
            method, request_url,
            params=params, data=dict_to_xml(data).encode('utf-8')
        )
        if response is None:
            return Result(return_code=self.codes.FAIL)
        result = xml_to_dict(response.content)
        return Result(
            return_msg=result['return_msg'],
            return_code=result['return_code'],
            result_code=result.get('result_code'),
            data=result
        )

    def get_jsapi_data(self, prepay_id):
        data = {
            'appId': self.app_id,
            'timeStamp': str(int(time.time())),
            'nonceStr': secrets.token_hex(16),
            'signType': 'MD5',
            'package': f'prepay_id={prepay_id}'
        }
        sign = calculate_signature(
            data,
            self.api_key if not self.is_sandbox else self.debug_api_key
        )
        data['paySign'] = sign.upper()
        return data

    def check_signature(self, data: typing.Dict) -> bool:
        return data['sign'] == calculate_signature(
            {
                k: v for k, v in data.items()
                if k not in ('sign',)
            },
            self.api_key if not self.is_sandbox else self.debug_api_key
        )

    def fetch_access_token(self):
        pass
