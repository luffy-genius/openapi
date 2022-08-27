

class OpenAPIException(Exception):
    pass


class DisallowedHost(OpenAPIException):
    pass


class NotFoundPath(OpenAPIException):
    pass
