import json
import hashlib
import typing

import OpenSSL
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus

from base64 import encodebytes, decodebytes
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256

from openapi.enums import IntegerChoices
from openapi.exceptions import NotFoundPath
from openapi.providers.base import BaseClient, BaseResult


class Code(IntegerChoices):
    SUCCESS = 0, '成功'
    FAIL = -1, '失败'


class Result(BaseResult):
    code: Code = Code.SUCCESS


def calculate_signature(unsigned_string, api_key):
    signer = PKCS1_v1_5.new(api_key)
    signature = signer.sign(SHA256.new(unsigned_string))
    # base64 编码，转换为unicode表示并移除回车
    return encodebytes(signature).decode('utf-8').replace('\n', '')


class Client(BaseClient):
    NAME = '支付宝'
    API_BASE_URL = 'https://openapi.alipay.com/gateway.do'
    API_VERSION = '1.0'

    def __init__(
        self, app_id,
        app_private_key_path, app_cert_public_key_path,
        alipay_root_cert_path, alipay_cert_public_key_path,
        is_sandbox=False
    ):
        super().__init__()
        self.API_BASE_URL = f'https://openapi.alipay{"dev" if is_sandbox else ""}.com/gateway.do'

        self.codes = Code
        self.app_id = app_id

        app_private_key_path = Path(app_private_key_path)
        if not app_private_key_path.exists():
            raise NotFoundPath(f'{app_private_key_path} not found')

        app_cert_public_key_path = Path(app_cert_public_key_path)
        if not app_cert_public_key_path.exists():
            raise NotFoundPath(f'{app_cert_public_key_path} not found')

        alipay_root_cert_path = Path(alipay_root_cert_path)
        if not alipay_root_cert_path.exists():
            raise NotFoundPath(f'{alipay_root_cert_path} not found')

        alipay_cert_public_key_path = Path(alipay_cert_public_key_path)
        if not alipay_cert_public_key_path.exists():
            raise NotFoundPath(f'{alipay_cert_public_key_path} not found')

        # 加载应用的私钥
        with open(app_private_key_path) as fp:
            self.app_private_key = RSA.importKey(fp.read())

        # 加载应用证书公钥
        with open(app_cert_public_key_path) as fp:
            self.app_cert_public_key = fp.read()

        # 加载阿里根证书
        with open(alipay_root_cert_path) as fp:
            self.alipay_root_cert = fp.read()

        # 加载ali证书公钥
        with open(alipay_cert_public_key_path) as fp:
            self.alipay_cert_public_key = fp.read()

    def fetch_access_token(self):
        pass

    def build_params(self, endpoint, data, notify_url=None, return_url=None):
        default = {
            'app_id': self.app_id,
            'method': endpoint,
            'charset': 'utf-8',
            'sign_type': 'RSA2',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'app_cert_sn': self.app_cert_sn,
            'alipay_root_cert_sn': self.root_cert_sn,
            'version': self.API_VERSION,
            'biz_content': data
        }

        if notify_url is not None:
            default['notify_url'] = notify_url

        if return_url is not None:
            default['return_url'] = return_url
        return default

    def build_query_params(self, data):
        ordered_items = sorted(
            ((k, v if not isinstance(v, dict) else json.dumps(v, separators=(',', ':')))
             for k, v in data.items())
        )
        unsigned_string = '&'.join(f'{k}={v}' for k, v in ordered_items)
        sign = calculate_signature(unsigned_string.encode('utf-8'), self.app_private_key)
        quoted_string = '&'.join(f'{k}={quote_plus(str(v).encode())}' for k, v in ordered_items)
        return f'{quoted_string}&sign={quote_plus(sign)}'

    def request(self, method, endpoint='', params=None, data=None):
        params = self.build_query_params(self.build_params(endpoint, params))
        response = self._request(method, f'{self.API_BASE_URL}?{params}')
        if response is not None:
            return Result(data=response.json()[f'{"_".join(endpoint.split("."))}_response'])
        else:
            return Result(code=self.codes.FAIL)

    @property
    def alipay_public_key(self):
        cert = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM, self.alipay_cert_public_key.encode('ascii')
        )
        return RSA.importKey(OpenSSL.crypto.dump_publickey(
            OpenSSL.crypto.FILETYPE_PEM, cert.get_pubkey()
        ).decode())

    @property
    def app_cert_sn(self):
        cert = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM, self.app_cert_public_key.encode('ascii')
        )
        cert_issue = cert.get_issuer()
        name = f'CN={cert_issue.CN},OU={cert_issue.OU},O={cert_issue.O},C={cert_issue.C}'
        m = hashlib.md5()
        m.update(bytes(f'{name}{cert.get_serial_number()}', encoding='utf-8'))
        return m.hexdigest()

    @property
    def root_cert_sn(self):
        root_cert_sn = None
        for cert in (
            OpenSSL.crypto.load_certificate(
                OpenSSL.crypto.FILETYPE_PEM, c.encode('ascii')
            )
            for c in self.alipay_root_cert.split('\n\n')
        ):
            try:
                alg = cert.get_signature_algorithm()
            except ValueError:
                continue
            if b'rsaEncryption' in alg or b'RSAEncryption' in alg:
                cert_issue = cert.get_issuer()
                name = f'CN={cert_issue.CN},OU={cert_issue.OU},O={cert_issue.O},C={cert_issue.C}'
                m = hashlib.md5()
                m.update(bytes(f'{name}{cert.get_serial_number()}', encoding="utf8"))
                cert_sn = m.hexdigest()
                if not root_cert_sn:
                    root_cert_sn = cert_sn
                else:
                    root_cert_sn = f'{root_cert_sn}_{cert_sn}'
        return root_cert_sn

    def check_signature(self, data: typing.Dict) -> bool:
        sign: str = data['sign']
        check_data = {
            k: v
            for k, v in data.items()
            if k not in ('sign', 'sign_type')
        }
        verify_data = sorted(
            ((k, v if not isinstance(v, dict) else json.dumps(v, separators=(',', ':'))) for k, v in check_data.items())
        )
        message = '&'.join(u'{}={}'.format(k, v) for k, v in verify_data)
        signer = PKCS1_v1_5.new(self.alipay_public_key)
        digest = SHA256.new()
        digest.update(message.encode())
        return bool(signer.verify(digest, decodebytes(sign.encode())))
