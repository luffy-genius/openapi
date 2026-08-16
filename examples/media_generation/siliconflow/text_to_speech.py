from pathlib import Path
from typing import Optional

from examples.media_generation import common
from openapi.providers.media_generation import AudioConfig, ModelProvider, TextToSpeechRequest

TEXT = '这是一段待合成语音的测试文案。'
VOICE = ''  # 已有持久音色 URI；与 REFERENCE_AUDIO_PATH 互斥
REFERENCE_AUDIO_PATH: Optional[str] = None  # 本地参考音频路径，如 '/path/to/sample.wav'
REFERENCE_TEXT: Optional[str] = None  # 参考音频对应文本，提供参考音频时必填
TITLE = '媒体联调测试'
AUDIO_CONFIG = AudioConfig()
PARAMETERS = {}


def execute():
    reference_audio = None
    if REFERENCE_AUDIO_PATH:
        reference_audio = Path(REFERENCE_AUDIO_PATH).expanduser().read_bytes()
    request = TextToSpeechRequest(
        text=TEXT,
        model=common.env_string('MEDIA_SILICONFLOW_MODEL', required=True),
        voice=VOICE,
        title=TITLE,
        audio_config=AUDIO_CONFIG,
        parameters=PARAMETERS,
        reference_audio=reference_audio,
        reference_text=REFERENCE_TEXT,
    )
    with common.media_client(ModelProvider.SILICONFLOW, 'speech') as media:
        return common.complete_result(media, media.speech.synthesize(request, provider=ModelProvider.SILICONFLOW))


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
