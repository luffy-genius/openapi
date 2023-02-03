import time
import secrets
from pathlib import Path
from typing import Optional, Union, Dict
from base64 import encodebytes
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256

from openapi.enums import TextChoices
from openapi.exceptions import NotFoundPath
from openapi.providers.base import BaseClient, BaseResult


def calculate_signature(unsigned_string, api_key):
    signer = PKCS1_v1_5.new(api_key)
    signature = signer.sign(SHA256.new(unsigned_string))
    # base64 编码，转换为unicode表示并移除回车
    return encodebytes(signature).decode('utf-8').replace('\n', '')


def format_params(data):
    return '&'.join([f'{k}={data[k]}' for k in sorted(data) if data[k] and k != 'sign'])


class Code(TextChoices):
    SUCCESS = '10000', 'OK'
    SIGN_FAIL = '401', '签名错误'
    FAIL = '500', '错误信息'


class Result(BaseResult):
    code: Union[Code, str] = Code.SUCCESS
    data: Optional[Dict]
    message: Optional[str]


class Client(BaseClient):
    NAME = '联想支付'
    VERSION = '1.0'
    API_BASE_URL = 'https://cloud-rest.lenovomm.com/cloud-intermodal-core/api/v1'

    def __init__(self, app_id, mch_id, private_key_path, public_key_path):
        super().__init__()
        self.app_id = app_id
        self.mch_id = mch_id
        self.codes = Code

        # public_key_path = Path(public_key_path)
        # if not public_key_path.exists():
        #     raise NotFoundPath(f'{public_key_path} not found')

        private_key_path = Path(private_key_path)
        if not private_key_path.exists():
            raise NotFoundPath(f'{private_key_path} not found')

        # 加载私钥
        with open(private_key_path) as fp:
            self.private_key = RSA.importKey(fp.read())

        self.public_key_path = public_key_path

    def request(self, endpoint: str, data: Dict, method: str = 'post') -> Result:
        public_params = {
            'mchId': self.mch_id,
            'appId': self.app_id,
            'nonce': secrets.token_hex(16),
            'timestamp': str(int(time.time() * 1000)),
            'version': self.VERSION,
            'signType': 'RSA2'
        }
        data.update(**public_params)

        data['sign'] = calculate_signature(
            format_params(data).encode(),
            self.private_key
        )
        request_url = f'{self.API_BASE_URL}{endpoint}'
        response = self._request(method, request_url, json=data)
        return Result(**response.json())

    def fetch_access_token(self):
        pass
