from typing import Protocol

from openapi.providers.media_generation.models import (
    ModelResult,
    TextOptimizationRequest,
    TextOutput,
)


class TextCapability(Protocol):
    def optimize_text(self, request: TextOptimizationRequest) -> ModelResult[TextOutput]: ...
