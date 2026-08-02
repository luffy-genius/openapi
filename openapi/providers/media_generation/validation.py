from typing import Any, Dict, TypeVar, Union

from pydantic import BaseModel

ModelT = TypeVar('ModelT', bound=BaseModel)


def coerce_model(value: Union[ModelT, Dict[str, Any]], model_class: type[ModelT]) -> ModelT:
    if isinstance(value, model_class):
        return value
    return model_class.model_validate(value)


def require_positive_integer(value: int, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f'{field} must be a positive integer')
