from examples.media_generation import common
from openapi.providers.media_generation import AudioConfig, ModelProvider, TranslateToSpeechRequest

TEXT = '这是一段待翻译并合成语音的测试文案。'
SOURCE_LANGUAGE = 'Chinese'
TARGET_LANGUAGE = 'English'
TITLE = '媒体联调测试'
TRANSLATION_PARAMETERS = {'temperature': 0.7}
SPEECH_PARAMETERS = {}

SPEECH_PROVIDERS = {
    'aliyun': ModelProvider.ALIYUN,
    'volcengine': ModelProvider.VOLCENGINE,
    'hifly': ModelProvider.HIFLY,
}

AUDIO_CONFIGS = {
    ModelProvider.ALIYUN: AudioConfig(format='wav', sample_rate=24000),
    ModelProvider.VOLCENGINE: AudioConfig(format='wav', sample_rate=24000),
    ModelProvider.HIFLY: AudioConfig(),
}


def execute():
    provider_name = common.env_string('MEDIA_WORKFLOW_SPEECH_PROVIDER', required=True)
    try:
        provider = SPEECH_PROVIDERS[provider_name]
    except KeyError as exc:
        choices = ', '.join(SPEECH_PROVIDERS)
        raise common.ExampleError(f'MEDIA_WORKFLOW_SPEECH_PROVIDER must be one of: {choices}') from exc
    provider_prefix = f'MEDIA_{provider.value.upper()}'
    request = TranslateToSpeechRequest(
        text=TEXT,
        source_language=SOURCE_LANGUAGE,
        target_language=TARGET_LANGUAGE,
        translation_model=common.env_string('MEDIA_DEEPSEEK_MODEL', required=True),
        speech_model=common.env_string(f'{provider_prefix}_SPEECH_MODEL', required=True),
        voice=common.env_string(f'{provider_prefix}_SPEECH_VOICE', required=True),
        title=TITLE,
        audio_config=AUDIO_CONFIGS[provider],
        translation_parameters=TRANSLATION_PARAMETERS,
        speech_parameters=SPEECH_PARAMETERS,
    )
    with common.workflow_client(provider) as media:
        result = media.workflow.translate_to_speech(
            request,
            text_provider=ModelProvider.DEEPSEEK,
            speech_provider=provider,
        )
        return common.complete_result(media, result)


def main() -> int:
    return common.run(execute)


if __name__ == '__main__':
    raise SystemExit(main())
