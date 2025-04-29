from datetime import datetime
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.hashes import MD5, Hash

from openapi.providers.base import BaseClient, BaseResult


def calculate_signature(params, secret):
    print(params)
    keys = list(params.keys())
    keys.sort()
    parameters = f"{secret}{str().join(f'{key}{params[key]}' for key in keys)}{secret}"
    h = Hash(algorithm=MD5(), backend=default_backend())
    h.update(parameters.encode('utf-8'))
    return h.finalize().hex().upper()


class Result(BaseResult):
    pass


class Client(BaseClient):
    NAME = '淘宝开放平台'
    VERSION = '2.0'
    API_BASE_URL = 'https://eco.taobao.com/router/rest'

    def __init__(self, app_id, secret):
        super().__init__()
        self.app_id = app_id
        self.secret = secret
        # hmac，md5，hmac-sha256
        self.sign_method = 'md5'

    def request(self, method, action, params=None, data=None, token_request=False):
        public_params = {
            'app_key': self.app_id,
            'method': action,
            'v': self.VERSION,
            'timestamp': datetime.now().strftime('%Y-%m-%d %X'),
            'partner_id': 'top-apitools',
            'session': '6100a040fa611a381b3cd37eca8a1c31df1ff56c6970e642212108025244',
            'format': 'json',
            'sign_method': self.sign_method,
        }
        public_params['sign'] = calculate_signature(
            {**public_params, **data},
            self.secret
        )
        response = self._request(method, self.API_BASE_URL, params={**public_params, **data}, json=data)
        print(response.json())
        return Result(**response.json())
