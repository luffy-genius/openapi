from examples.media_generation import common
from openapi.providers.media_generation import MediaClient


def execute():
    task_ref = common.load_task_ref()
    config = common.provider_config(task_ref.provider, common.capability_for_task(task_ref))
    with MediaClient.create(config) as media:
        return common.complete_result(media, media.task.get(task_ref))


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
