from typing import Optional, Union, List, Dict
from datetime import datetime

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str]
    expires_in: int = 7200
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def is_valid(self):
        return (datetime.now() - self.created_at).total_seconds() < (self.expires_in - self.expires_in * 0.3)


class BaseResult(BaseModel):
    code: int
    data: Optional[Union[List, Dict]]
    message: Optional[str]


class BaseClient:

    API_BASE_URL = None
    API_VERSION = None

    def __init__(self):
        self._token: Optional[Token] = None

    def fetch_access_token(self):
        raise NotImplementedError()

    def refresh_access_token(self):
        pass

    @property
    def access_token(self):
        if not (self._token and self._token.is_valid):
            self.fetch_access_token()
        return self._token.access_token if self._token is not None else ''
