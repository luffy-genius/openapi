from openapi.exceptions import OpenAPIException


class MediaGenerationError(OpenAPIException):
    """Base exception for the media generation SDK."""


class ConfigurationError(MediaGenerationError):
    """A requested provider or credential has not been configured."""


class UnsupportedCapabilityError(MediaGenerationError):
    """The selected provider does not implement the requested operation."""


class ProviderAPIError(MediaGenerationError):
    """A provider rejected a request or returned an invalid response."""


class GenerationTimeoutError(MediaGenerationError):
    """Polling exceeded the local timeout; the remote task is not cancelled."""
