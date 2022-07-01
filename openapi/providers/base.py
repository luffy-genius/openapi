import httpx

from datetime import datetime
from typing import Optional


class Token:

    def __init__(self, token, refresh_token, expires_in=7200):
        self.token = token
        self.refresh_token = refresh_token
        self.expires_in = expires_in
        self.created_at = datetime.now()

    @property
    def is_valid(self):
        return (datetime.now() - self.created_at).total_seconds() > (self.expires_in - self.expires_in * 0.2)


class BaseClient:

    API_BASE_URL = None
    API_VERSION = None

    def __init__(self):
        self._token: Optional[Token] = None

    def fetch_access_token(self):
        raise NotImplementedError()

    @property
    def access_token(self):
        if not (self._token and self._token.is_valid):
            self.fetch_access_token()
        return self._token.token
