from examples.media_generation import common
from openapi.providers.media_generation import DigitalHumanRequest, ModelProvider

TEXT = '这是一段待合成语音的测试文案。'
TITLE = '媒体联调测试'
AUDIO_URL = 'https://cdn.example.com/speech.mp3'
PARAMETERS = {}


def execute():
    values = (
        {'audio_url': AUDIO_URL}
        if AUDIO_URL
        else {
            'text': TEXT,
            'voice': common.env_string('MEDIA_HIFLY_SPEECH_VOICE', required=True),
        }
    )
    request = DigitalHumanRequest(
        avatar=common.env_string('MEDIA_HIFLY_AVATAR_ID', required=True),
        title=TITLE,
        model=common.env_string('MEDIA_HIFLY_DIGITAL_HUMAN_MODEL'),
        parameters=PARAMETERS,
        **values,
    )
    with common.media_client(ModelProvider.HIFLY, 'digital_human') as media:
        result = media.avatar.render(request, provider=ModelProvider.HIFLY)
        return common.complete_result(media, result)


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
