import time
import json
import hashlib
from typing import Mapping, Any, Generic

from openapi.providers.base import BaseClient, BaseResult, T


"""
DocRef: https://help.polyv.net/#/vod/api/playsafe/token/create_token
"""


class Result(BaseResult, Generic[T]):
    code: int
    status: str


class Client(BaseClient):
    NAME = 'Polyv'
    API_BASE_URL = 'https://hls.videocc.net'

    def __init__(self, user_id: str, secret: str):
        super().__init__()
        self.user_id = user_id
        self.secret = secret

    def request(
        self, method: str, endpoint: str, data: Mapping[str, Any],
        *, model: T | None = None
    ) -> Result:
        request_data = {
            'userId': self.user_id,
            'ts': int(time.time() * 1000),
        }
        request_data.update(**data)
        ordered_data = sorted(
            (
                (k, v if not isinstance(v, dict) else json.dumps(v, separators=(',', ':')))
                for k, v in request_data.items()
            )
        )
        sign_string = '{}{}{}'.format(
            self.secret,
            "".join(["{}{}".format(item[0], item[1]) for item in ordered_data]),
            self.secret,
        )

        h = hashlib.md5()
        h.update(sign_string.encode())
        request_data['sign'] = h.hexdigest().upper()

        response = self._request(
            method, f'{self.API_BASE_URL}{endpoint}',
            data=request_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        response.raise_for_status()
        payload = response.json()
        return Result[model].model_validate(payload) if model else Result.model_validate(payload)  # noqa
