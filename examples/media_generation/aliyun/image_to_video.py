from examples.media_generation import common
from openapi.providers.media_generation import ImageToVideoRequest, ModelProvider

SOURCE_IMAGE_URL = 'https://cdn.example.com/source.png'
PROMPT = '一只戴飞行员护目镜的橘猫，电影光影'
LAST_IMAGE_URL = None
DURATION = 5
RESOLUTION = '720P'
RATIO = '16:9'
SEED = None
WATERMARK = True
PARAMETERS = {}


def execute():
    request = ImageToVideoRequest(
        image=SOURCE_IMAGE_URL,
        prompt=PROMPT,
        last_image=LAST_IMAGE_URL,
        model=common.env_string('MEDIA_ALIYUN_VIDEO_MODEL'),
        duration=DURATION,
        resolution=RESOLUTION,
        ratio=RATIO,
        seed=SEED,
        watermark=WATERMARK,
        parameters=PARAMETERS,
    )
    with common.media_client(ModelProvider.ALIYUN, 'video') as media:
        return common.complete_result(media, media.video.from_image(request, provider=ModelProvider.ALIYUN))


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
