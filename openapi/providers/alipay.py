import json
import httpx
import hashlib
import OpenSSL
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus

from base64 import encodebytes
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256

from ..exceptions import NotFoundPath
from .base import BaseClient, BaseResult, Token


def calculate_signature(params, api_key):
    ordered_items = sorted(
        ((k, v if not isinstance(v, dict) else json.dumps(v, separators=(',', ':')))
         for k, v in params.items())
    )
    unsigned_string = '&'.join('{0}={1}'.format(k, v) for k, v in ordered_items)
    signer = PKCS1_v1_5.new(api_key)
    signature = signer.sign(SHA256.new(unsigned_string.encode('utf-8')))
    # base64 编码，转换为unicode表示并移除回车
    sign = encodebytes(signature).decode('utf-8').replace('\n', '')
    return sign


class Client(BaseClient):
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

        self.app_id = app_id

        app_private_key_path = Path(app_private_key_path)
        if not app_private_key_path.exists():
            raise NotFoundPath(f'{app_private_key_path} not found')

        app_cert_public_key_path = Path(app_cert_public_key_path)
        if not app_cert_public_key_path.exists():
            raise NotFoundPath(f'{app_private_key_path} not found')

        alipay_root_cert_path = Path(alipay_root_cert_path)
        if not alipay_root_cert_path.exists():
            raise NotFoundPath(f'{app_private_key_path} not found')

        alipay_cert_public_key_path = Path(alipay_cert_public_key_path)
        if not alipay_cert_public_key_path.exists():
            raise NotFoundPath(f'{app_private_key_path} not found')

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
        sign = calculate_signature(data, self.app_private_key)
        quoted_string = '&'.join('{0}={1}'.format(k, quote_plus(v)) for k, v in data)
        signed_string = f'{quoted_string}&sign={quote_plus(sign)}'
        return signed_string

    def request(self, method, endpoint='', params=None, data=''):
        pass

    @property
    def alipay_public_key(self):
        cert = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM, self.alipay_cert_public_key.encode('ascii')
        )
        return OpenSSL.crypto.dump_publickey(
            OpenSSL.crypto.FILETYPE_PEM, cert.get_pubkey()
        ).decode('utf-8')

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
