from examples.media_generation import common
from openapi.providers.media_generation import AvatarCloneRequest, ModelProvider

TITLE = '媒体联调测试'
IMAGE_URL = 'https://cdn.example.com/avatar.png'
VIDEO_URL = None
AIGC_FLAG = None
PARAMETERS = {}


def execute():
    if bool(IMAGE_URL) == bool(VIDEO_URL):
        raise common.ExampleError('exactly one of IMAGE_URL and VIDEO_URL must be set in this script')
    request = AvatarCloneRequest(
        title=TITLE,
        image_url=IMAGE_URL,
        video_url=VIDEO_URL,
        aigc_flag=AIGC_FLAG,
        parameters=PARAMETERS,
    )
    with common.media_client(ModelProvider.HIFLY, 'avatar_clone') as media:
        result = media.avatar.clone(request, provider=ModelProvider.HIFLY)
        return common.complete_result(media, result)


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
