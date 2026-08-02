"""Unified media client examples. Credentials are never read implicitly."""

from openapi.providers.media_generation import (
    AliyunConfig,
    AudioConfig,
    DeepSeekConfig,
    DigitalHumanRequest,
    HiFlyConfig,
    ImageGenerationRequest,
    ImageToVideoRequest,
    MediaClient,
    ModelProvider,
    TextOptimizationRequest,
    TextToSpeechRequest,
    TranslateToSpeechRequest,
    VolcengineConfig,
    VolcengineSpeechConfig,
)

media = MediaClient.create(
    VolcengineConfig(
        ark_api_key='your-ark-key',
        access_key='your-volcengine-ak',
        secret_key='your-volcengine-sk',
        speech=VolcengineSpeechConfig(app_id='your-speech-app-id', access_token='your-speech-token'),
    ),
    AliyunConfig(api_key='your-bailian-key', workspace_id='your-workspace-id'),
    HiFlyConfig(token='your-hifly-token'),
    DeepSeekConfig(api_key='your-deepseek-key'),
)

try:
    text = media.text.optimize(
        TextOptimizationRequest(text='这是一段待润色的文案。', model='your-deepseek-model'),
        provider=ModelProvider.DEEPSEEK,
    )
    print(text.output.text)

    image = media.image.generate(
        ImageGenerationRequest(prompt='一只戴飞行员护目镜的橘猫，电影光影', size='2K'),
        provider=ModelProvider.VOLCENGINE,
    )
    print(image.output.urls)

    video = media.video.from_image(
        ImageToVideoRequest(
            image='https://cdn.example.com/cat.png',
            prompt='橘猫抬头看向天空，镜头缓慢推进',
            duration=5,
            resolution='720P',
        ),
        provider=ModelProvider.ALIYUN,
    )
    print(media.task.wait(video.task_ref, timeout=1800, poll_interval=5).output.urls)

    speech = media.speech.synthesize(
        TextToSpeechRequest(
            text='Hello from the media client.',
            model='qwen-audio-3.0-tts-flash',
            voice='longanhuan_v3.6',
            language='en',
            audio_config=AudioConfig(format='wav', sample_rate=24000),
        ),
        provider=ModelProvider.ALIYUN,
    )
    print(speech.output.urls or [speech.output.audio_base64])

    translated = media.workflow.translate_to_speech(
        TranslateToSpeechRequest(
            text='今天天气很好。',
            source_language='Chinese',
            target_language='English',
            translation_model='your-deepseek-model',
            speech_model='qwen-audio-3.0-tts-flash',
            voice='longanhuan_v3.6',
        ),
        text_provider=ModelProvider.DEEPSEEK,
        speech_provider=ModelProvider.ALIYUN,
    )
    print(translated.output.urls or [translated.output.audio_base64])

    digital_human = media.avatar.render(
        DigitalHumanRequest(
            avatar='your-avatar-id',
            audio_url='https://cdn.example.com/speech.mp3',
            title='产品介绍',
        ),
        provider=ModelProvider.HIFLY,
    )
    print(digital_human.task_ref.to_json())
finally:
    media.close()
