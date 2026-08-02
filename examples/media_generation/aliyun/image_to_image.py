from examples.media_generation import common
from openapi.providers.media_generation import ImageGenerationRequest, ModelProvider

PROMPT = '一只戴飞行员护目镜的橘猫，电影光影'
NEGATIVE_PROMPT = None
SOURCE_IMAGE_URL = 'https://cdn.example.com/source.png'
IMAGE_SIZE = '2K'
IMAGE_COUNT = 1
SEED = None
WATERMARK = True
PARAMETERS = {}


def execute():
    request = ImageGenerationRequest(
        prompt=PROMPT,
        images=[SOURCE_IMAGE_URL],
        model=common.env_string('MEDIA_ALIYUN_IMAGE_MODEL'),
        size=IMAGE_SIZE,
        n=IMAGE_COUNT,
        seed=SEED,
        watermark=WATERMARK,
        negative_prompt=NEGATIVE_PROMPT,
        parameters=PARAMETERS,
    )
    with common.media_client(ModelProvider.ALIYUN, 'image') as media:
        return common.complete_result(media, media.image.edit(request, provider=ModelProvider.ALIYUN))


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
