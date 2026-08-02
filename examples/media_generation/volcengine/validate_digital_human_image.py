from examples.media_generation import common
from openapi.providers.media_generation import ModelProvider

IMAGE_URL = 'https://cdn.example.com/person.png'


def execute():
    with common.media_client(ModelProvider.VOLCENGINE, 'image_validation') as media:
        result = media.avatar.validate_image(IMAGE_URL, provider=ModelProvider.VOLCENGINE)
        return common.complete_result(media, result)


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
