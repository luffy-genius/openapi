import secrets
import time
from base64 import decodebytes, encodebytes
from pathlib import Path
from typing import Dict

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

from openapi.enums import TextChoices
from openapi.exceptions import NotFoundPath
from openapi.providers.base import BaseClient, BaseResult


def format_params(data):
    return '&'.join([f'{k}={data[k]}' for k in sorted(data) if data[k] and k != 'sign'])


def calculate_signature(unsigned_string, api_key):
    signer = PKCS1_v1_5.new(api_key)
    signature = signer.sign(SHA256.new(unsigned_string))
    # base64 编码，转换为unicode表示并移除回车
    return encodebytes(signature).decode('utf-8').replace('\n', '')


def verify_signature(params, api_key, charset='utf-8'):
    sign = params['sign']
    string = format_params(params)
    signer = PKCS1_v1_5.new(api_key)
    digest = SHA256.new()
    digest.update(string.encode(charset))
    return signer.verify(digest, decodebytes(sign.encode(charset)))


class Code(TextChoices):
    SUCCESS = '10000', 'OK'
    SIGN_FAIL = '401', '签名错误'
    FAIL = '500', '错误信息'


class Result(BaseResult):
    code: Code | str = Code.SUCCESS
    data: Dict | None = None
    message: str | None = None


class Client(BaseClient):
    NAME = '联想支付'
    VERSION = '1.0'
    API_BASE_URL = 'https://cloud-rest.lenovomm.com/cloud-intermodal-core/api/v1'

    def __init__(self, app_id, mch_id, private_key_path, public_key_path):
        super().__init__()
        self.app_id = app_id
        self.mch_id = mch_id
        self.codes = Code

        public_key_path = Path(public_key_path)
        if not public_key_path.exists():
            raise NotFoundPath(f'{public_key_path} not found')

        private_key_path = Path(private_key_path)
        if not private_key_path.exists():
            raise NotFoundPath(f'{private_key_path} not found')

        # 加载公钥
        with open(public_key_path) as fp:
            self.public_key = RSA.importKey(fp.read())

        # 加载私钥
        with open(private_key_path) as fp:
            self.private_key = RSA.importKey(fp.read())

    def request(self, endpoint: str, data: Dict, method: str = 'post') -> Result:
        public_params = {
            'mchId': self.mch_id,
            'appId': self.app_id,
            'nonce': secrets.token_hex(16),
            'timestamp': str(int(time.time() * 1000)),
            'version': self.VERSION,
            'signType': 'RSA2',
        }
        data.update(**public_params)

        data['sign'] = calculate_signature(format_params(data).encode(), self.private_key)
        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, json=data)
        return Result(**response.json())

    def check_signature(self, data: Dict) -> bool:
        data.setdefault('appId', self.app_id)
        data.setdefault('mchId', self.app_id)
        return bool(verify_signature(data, self.public_key))

    def fetch_access_token(self):
        pass
