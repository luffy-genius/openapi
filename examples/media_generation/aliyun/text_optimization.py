from examples.media_generation import common
from openapi.providers.media_generation import (
    ModelProvider,
    TextOptimizationAction,
    TextOptimizationRequest,
    TextOptimizationStyle,
)

TEXT = '这是一段待润色的测试文案。'
ACTION = TextOptimizationAction.EXPAND
STYLE = TextOptimizationStyle.PROFESSIONAL
INSTRUCTION = 'Keep the output in the same language as the input. Do not translate it.'
PARAMETERS = {'temperature': 0.7}


def execute():
    request = TextOptimizationRequest(
        text=TEXT,
        model=common.env_string('MEDIA_ALIYUN_TEXT_MODEL', required=True),
        action=ACTION,
        style=STYLE,
        instruction=INSTRUCTION,
        parameters=PARAMETERS,
    )
    with common.media_client(ModelProvider.ALIYUN, 'text') as media:
        result = media.text.optimize(request, provider=ModelProvider.ALIYUN)
        return common.complete_result(media, result)


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
