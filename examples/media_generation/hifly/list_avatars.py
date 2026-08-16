from examples.media_generation import common
from openapi.providers.media_generation import ModelProvider

PAGE = 1
PAGE_SIZE = 20


def execute():
    with common.media_client(ModelProvider.HIFLY, 'avatar_list') as media:
        result = media.avatar.list(
            provider=ModelProvider.HIFLY,
            page=PAGE,
            size=PAGE_SIZE,
        )
        return common.complete_result(media, result)


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
