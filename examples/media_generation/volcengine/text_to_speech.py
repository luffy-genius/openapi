from examples.media_generation import common
from openapi.providers.media_generation import AudioConfig, ModelProvider, TextToSpeechRequest

TEXT = '这是一段待合成语音的测试文案。'
LANGUAGE = 'zh-CN'
TITLE = '媒体联调测试'
AUDIO_CONFIG = AudioConfig(format='wav', sample_rate=24000)
PARAMETERS = {}


def execute():
    request = TextToSpeechRequest(
        text=TEXT,
        model=common.env_string('MEDIA_VOLCENGINE_SPEECH_MODEL', required=True),
        voice=common.env_string('MEDIA_VOLCENGINE_SPEECH_VOICE', required=True),
        language=LANGUAGE,
        title=TITLE,
        audio_config=AUDIO_CONFIG,
        parameters=PARAMETERS,
    )
    with common.media_client(ModelProvider.VOLCENGINE, 'speech') as media:
        return common.complete_result(media, media.speech.synthesize(request, provider=ModelProvider.VOLCENGINE))


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
