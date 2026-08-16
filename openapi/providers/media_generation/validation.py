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


# SiliconFlow create-speech option contract, per the official API reference:
# https://docs.siliconflow.com/en/api-reference/audio/create-speech
SILICONFLOW_RESPONSE_FORMATS = {'mp3', 'opus', 'wav', 'pcm'}
SILICONFLOW_SAMPLE_RATES = {8000, 16000, 24000, 32000, 44100, 48000}
SILICONFLOW_SAMPLE_RATES_BY_FORMAT = {
    'mp3': {32000, 44100},
    'opus': {48000},
    'wav': {8000, 16000, 24000, 32000, 44100},
    'pcm': {8000, 16000, 24000, 32000, 44100},
}
SILICONFLOW_SPEED_RANGE = (0.25, 4.0)
SILICONFLOW_GAIN_RANGE = (-10.0, 10.0)


def validate_siliconflow_speech_options(
    *,
    response_format: str,
    sample_rate: int,
    speed: float,
    gain: float,
) -> None:
    """Validate the resolved SiliconFlow speech options against the official contract."""
    if response_format not in SILICONFLOW_RESPONSE_FORMATS:
        allowed = ', '.join(sorted(SILICONFLOW_RESPONSE_FORMATS))
        raise ValueError(f'response_format must be one of {allowed}: {response_format!r}')
    if sample_rate not in SILICONFLOW_SAMPLE_RATES:
        allowed = ', '.join(str(rate) for rate in sorted(SILICONFLOW_SAMPLE_RATES))
        raise ValueError(f'sample_rate must be one of {allowed}: {sample_rate!r}')
    allowed_rates = SILICONFLOW_SAMPLE_RATES_BY_FORMAT[response_format]
    if sample_rate not in allowed_rates:
        allowed = ', '.join(str(rate) for rate in sorted(allowed_rates))
        raise ValueError(
            f'sample_rate {sample_rate} is not supported for response_format {response_format}; '
            f'allowed rates are {allowed}'
        )
    low, high = SILICONFLOW_SPEED_RANGE
    if not low <= speed <= high:
        raise ValueError(f'speed must be within [{low}, {high}]: {speed!r}')
    low, high = SILICONFLOW_GAIN_RANGE
    if not low <= gain <= high:
        raise ValueError(f'gain must be within [{low}, {high}]: {gain!r}')
