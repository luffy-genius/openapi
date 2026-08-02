from examples.media_generation import common
from openapi.providers.media_generation import DigitalHumanRequest, ModelProvider

IMAGE_URL = 'https://cdn.example.com/person.png'
AUDIO_URL = 'https://cdn.example.com/speech.mp3'
PROMPT = '一只戴飞行员护目镜的橘猫，电影光影'
RESOLUTION = '720P'
SEED = None
PARAMETERS = {}


def execute():
    request = DigitalHumanRequest(
        image_url=IMAGE_URL,
        audio_url=AUDIO_URL,
        prompt=PROMPT,
        model=common.env_string('MEDIA_VOLCENGINE_DIGITAL_HUMAN_MODEL'),
        resolution=RESOLUTION,
        seed=SEED,
        parameters=PARAMETERS,
    )
    with common.media_client(ModelProvider.VOLCENGINE, 'digital_human') as media:
        return common.complete_result(media, media.avatar.render(request, provider=ModelProvider.VOLCENGINE))


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
