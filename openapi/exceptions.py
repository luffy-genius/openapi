from httpx import HTTPError


class OpenAPIException(Exception):
    pass


class DisallowedHost(OpenAPIException):
    pass


class NotFoundPath(OpenAPIException):
    pass


class OpenAPIHttpError(OpenAPIException, HTTPError):
    pass
