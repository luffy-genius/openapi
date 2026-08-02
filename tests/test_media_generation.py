import importlib.util
import json
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError

import openapi.providers.media_generation as media_generation
from openapi.exceptions import OpenAPIException
from openapi.providers.media_generation import (
    AliyunConfig,
    AudioConfig,
    AudioOutput,
    AvatarCloneRequest,
    AvatarListOutput,
    ConfigurationError,
    DeepSeekConfig,
    DigitalHumanRequest,
    GenerationTimeoutError,
    HiFlyConfig,
    ImageGenerationRequest,
    ImageToVideoRequest,
    ImageValidationOutput,
    MediaClient,
    MediaOutput,
    ModelOperation,
    ModelProvider,
    ModelResult,
    ModelStatus,
    ProviderAPIError,
    TaskRef,
    TextOptimizationAction,
    TextOptimizationRequest,
    TextOptimizationStyle,
    TextOutput,
    TextToSpeechRequest,
    TranslateToSpeechRequest,
    UnsupportedCapabilityError,
    VolcengineConfig,
    VolcengineSpeechConfig,
)


class RecordingTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        if response[0] == 'connect_error':
            raise httpx.ConnectError(response[1], request=request)
        if response[0] == 'read_timeout':
            raise httpx.ReadTimeout(response[1], request=request)
        status, payload, *headers = response
        return httpx.Response(status, json=payload, headers=headers[0] if headers else None, request=request)


def make_client(transport, **configs):
    client = httpx.Client(transport=httpx.MockTransport(transport))
    media = MediaClient.create(*configs.values(), http_client=client, sleep=lambda _: None)
    return media, client


class FakeVisualService:
    def __init__(self):
        self.ak = None
        self.sk = None
        self.calls = []
        self.task_status = 'done'

    def set_ak(self, value):
        self.ak = value

    def set_sk(self, value):
        self.sk = value

    def cv_process(self, body):
        self.calls.append(('validate', body))
        return {'code': 10000, 'data': {'resp_data': json.dumps({'status': 1, 'face': 'ok'})}}

    def cv_sync2async_submit_task(self, body):
        self.calls.append(('submit', body))
        return {'code': 10000, 'data': {'task_id': 'omni-1'}}

    def cv_sync2async_get_result(self, body):
        self.calls.append(('query', body))
        return {'code': 10000, 'data': {'status': self.task_status, 'video_url': 'https://out/omni.mp4'}}


class ModelTests(unittest.TestCase):
    def test_media_client_exposes_domain_interfaces_without_legacy_gateway_methods(self):
        media, client = make_client(RecordingTransport([]))
        self.addCleanup(client.close)
        for name in ('text', 'speech', 'image', 'video', 'avatar', 'task', 'workflow'):
            self.assertTrue(hasattr(media, name))
        for name in ('optimize_text', 'text_to_speech', 'translate_to_speech', 'get_task', 'wait'):
            self.assertFalse(hasattr(media, name))
        self.assertFalse(hasattr(media_generation, 'ModelGateway'))

    def test_media_client_rejects_duplicate_provider_configuration(self):
        client = httpx.Client(transport=httpx.MockTransport(RecordingTransport([])))
        self.addCleanup(client.close)
        with self.assertRaisesRegex(ConfigurationError, 'configured more than once'):
            MediaClient.create(
                DeepSeekConfig(api_key='first'),
                DeepSeekConfig(api_key='second'),
                http_client=client,
            )

    def test_secrets_are_required_nonempty_and_masked(self):
        with self.assertRaises(ValidationError):
            DeepSeekConfig()
        with self.assertRaises(ValidationError):
            DeepSeekConfig(api_key='')
        with self.assertRaises(ValidationError):
            AliyunConfig(api_key=None)
        with self.assertRaises(ValidationError):
            HiFlyConfig(token='')
        with self.assertRaises(ValidationError):
            VolcengineConfig()
        with self.assertRaises(ValidationError):
            VolcengineConfig(access_key='ak')

        config = VolcengineConfig(
            ark_api_key='ark-secret',
            speech=VolcengineSpeechConfig(app_id='app', access_token='speech-secret'),
        )
        serialized = config.model_dump_json()
        self.assertNotIn('ark-secret', repr(config))
        self.assertNotIn('ark-secret', serialized)
        self.assertNotIn('speech-secret', serialized)
        self.assertIn('**********', serialized)

    def test_deepseek_url_must_be_https(self):
        with self.assertRaisesRegex(ValidationError, 'HTTPS'):
            DeepSeekConfig(api_key='key', base_url='http://api.example.com')
        config = DeepSeekConfig(api_key='key', base_url='https://host.example.com/')
        self.assertEqual(config.base_url, 'https://host.example.com')

    def test_text_and_audio_request_validation(self):
        with self.assertRaises(ValidationError):
            TextOptimizationRequest(text=' ', model='model')
        with self.assertRaises(ValidationError):
            TextOptimizationRequest(text='text', model='model', action='translate')
        with self.assertRaises(ValidationError):
            TextOptimizationRequest(text='text', model='model', target_language='English')
        with self.assertRaisesRegex(ValidationError, 'reserved fields'):
            TextOptimizationRequest(text='text', model='model', parameters={'stream': True})
        with self.assertRaises(ValidationError):
            TextToSpeechRequest(text='text', model='', voice='voice')
        with self.assertRaisesRegex(ValidationError, 'reserved fields'):
            TextToSpeechRequest(text='text', model='tts', voice='voice', parameters={'text': 'other'})
        with self.assertRaisesRegex(ValidationError, 'reserved fields'):
            TextToSpeechRequest(text='text', model='tts', voice='voice', parameters={'sample_rate': 8000})
        with self.assertRaises(ValidationError):
            AudioConfig(sample_rate=12345)

    def test_audio_rate_multipliers_accept_boundaries_and_reject_out_of_range(self):
        minimum = AudioConfig(speech_rate=0.5, loudness_rate=0.1, pitch_rate=0.5)
        maximum = AudioConfig(speech_rate=2.0, loudness_rate=2.0, pitch_rate=2.0)
        self.assertEqual((minimum.speech_rate, minimum.loudness_rate, minimum.pitch_rate), (0.5, 0.1, 0.5))
        self.assertEqual((maximum.speech_rate, maximum.loudness_rate, maximum.pitch_rate), (2.0, 2.0, 2.0))
        for field, value in (
            ('speech_rate', 0.49),
            ('speech_rate', 2.01),
            ('loudness_rate', 0.09),
            ('loudness_rate', 2.01),
            ('pitch_rate', 0.49),
            ('pitch_rate', 2.01),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                AudioConfig(**{field: value})

    def test_task_ref_json_and_legacy_operation_restore(self):
        old = '{"provider":"aliyun","operation":"image_generation","task_id":"old-task"}'
        restored = TaskRef.from_json(old)
        self.assertEqual(restored.operation, ModelOperation.TEXT_TO_IMAGE)
        self.assertEqual(TaskRef.from_json(restored.to_json()), restored)
        with self.assertRaises(ValidationError):
            TaskRef(provider='aliyun', operation='typo', task_id='task')

    def test_model_result_done_and_parameterized_output(self):
        result = ModelResult[TextOutput](
            provider='deepseek',
            operation='text_optimization',
            status='succeeded',
            output=TextOutput(text='done'),
        )
        self.assertTrue(result.done)
        self.assertIsInstance(result.output, TextOutput)
        queued = ModelResult[MediaOutput](provider='aliyun', operation='image_to_video', status='queued')
        self.assertFalse(queued.done)
        self.assertIsNone(queued.output)

    def test_errors_follow_existing_exception_hierarchy(self):
        for error_type in (
            ConfigurationError,
            GenerationTimeoutError,
            ProviderAPIError,
            UnsupportedCapabilityError,
        ):
            with self.subTest(error_type=error_type):
                self.assertTrue(issubclass(error_type, OpenAPIException))

    @unittest.skipUnless(importlib.util.find_spec('inflection'), 'legacy Aliyun dependencies are not installed')
    def test_legacy_aliyun_client_is_unchanged(self):
        from openapi.providers.aliyun import Client as LegacyAliyunClient

        client = LegacyAliyunClient('legacy-app-id', 'legacy-secret')
        self.assertEqual(client.app_id, 'legacy-app-id')
        self.assertEqual(client.secret, 'legacy-secret')


class TextOptimizationTests(unittest.TestCase):
    def test_volcengine_auth_endpoint_model_parameters_and_prompt(self):
        transport = RecordingTransport([(200, {'choices': [{'message': {'content': '润色结果'}}]})])
        media, client = make_client(transport, volcengine=VolcengineConfig(ark_api_key='ark-key'))
        self.addCleanup(client.close)

        result = media.text.optimize(
            TextOptimizationRequest(
                text='原文',
                model='doubao-text',
                action=TextOptimizationAction.EXPAND,
                style=TextOptimizationStyle.FRIENDLY,
                instruction='不要使用禁用词',
                parameters={'temperature': 0.3, 'max_tokens': 100},
            ),
            provider='volcengine',
        )

        request = transport.requests[0]
        body = json.loads(request.content)
        self.assertEqual(str(request.url), 'https://ark.cn-beijing.volces.com/api/v3/chat/completions')
        self.assertEqual(request.headers['authorization'], 'Bearer ark-key')
        self.assertEqual(body['model'], 'doubao-text')
        self.assertEqual(body['temperature'], 0.3)
        self.assertFalse(body['stream'])
        self.assertIn('friendly', body['messages'][1]['content'])
        self.assertIn('禁用词', body['messages'][1]['content'])
        self.assertEqual(result.provider, ModelProvider.VOLCENGINE)
        self.assertEqual(result.output.text, '润色结果')

    def test_aliyun_workspace_compatible_endpoint_and_translation(self):
        transport = RecordingTransport([(200, {'choices': [{'message': {'content': 'Hello'}}]})])
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace'))
        self.addCleanup(client.close)

        result = media.text.optimize(
            TextOptimizationRequest(text='你好', model='qwen-text', action='translate', target_language='English'),
            provider='aliyun',
        )

        request = transport.requests[0]
        self.assertEqual(request.url.host, 'workspace.cn-beijing.maas.aliyuncs.com')
        self.assertEqual(request.url.path, '/compatible-mode/v1/chat/completions')
        self.assertEqual(request.headers['authorization'], 'Bearer ali-key')
        self.assertIn('English', json.loads(request.content)['messages'][1]['content'])
        self.assertEqual(result.output.text, 'Hello')

    def test_deepseek_official_and_custom_endpoint(self):
        for base_url in ('https://api.deepseek.com', 'https://deepseek.example.com/openai/'):
            with self.subTest(base_url=base_url):
                transport = RecordingTransport([(200, {'choices': [{'message': {'content': 'better'}}]})])
                media, client = make_client(
                    transport, deepseek=DeepSeekConfig(api_key='deep-secret', base_url=base_url)
                )
                self.addCleanup(client.close)
                result = media.text.optimize(
                    TextOptimizationRequest(text='draft', model='deepseek-model'), provider='deepseek'
                )
                expected_path = '/openai/chat/completions' if 'openai' in base_url else '/chat/completions'
                self.assertEqual(transport.requests[0].url.path, expected_path)
                self.assertEqual(transport.requests[0].headers['authorization'], 'Bearer deep-secret')
                self.assertEqual(result.output.text, 'better')

    def test_hifly_and_deepseek_media_are_unsupported(self):
        transport = RecordingTransport([])
        media, client = make_client(
            transport,
            hifly=HiFlyConfig(token='token'),
            deepseek=DeepSeekConfig(api_key='key'),
        )
        self.addCleanup(client.close)
        with self.assertRaises(UnsupportedCapabilityError):
            media.text.optimize(TextOptimizationRequest(text='text', model='model'), provider='hifly')
        with self.assertRaises(UnsupportedCapabilityError):
            media.image.generate(ImageGenerationRequest(prompt='cat'), provider='deepseek')

    def test_missing_content_and_billable_failure_are_not_retried(self):
        missing = RecordingTransport([(200, {'choices': []})])
        media, client = make_client(missing, deepseek=DeepSeekConfig(api_key='key'))
        self.addCleanup(client.close)
        with self.assertRaisesRegex(ProviderAPIError, 'did not contain'):
            media.text.optimize(TextOptimizationRequest(text='text', model='model'), provider='deepseek')

        failing = RecordingTransport([(503, {'message': 'busy'})])
        media, client = make_client(failing, deepseek=DeepSeekConfig(api_key='key'))
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError):
            media.text.optimize(TextOptimizationRequest(text='text', model='model'), provider='deepseek')
        self.assertEqual(len(failing.requests), 1)


class SpeechTests(unittest.TestCase):
    def test_volcengine_audio_config_base64_and_log_id(self):
        transport = RecordingTransport(
            [(200, {'code': 3000, 'data': 'BASE64_AUDIO', 'duration': 1200}, {'X-Tt-Logid': 'log-1'})]
        )
        config = VolcengineConfig(speech=VolcengineSpeechConfig(app_id='speech-app', access_token='speech-token'))
        media, client = make_client(transport, volcengine=config)
        self.addCleanup(client.close)

        result = media.speech.synthesize(
            TextToSpeechRequest(
                text='你好',
                model='volcano_tts',
                voice='voice-one',
                language='zh-cn',
                audio_config=AudioConfig(
                    format='mp3',
                    sample_rate=24000,
                    speech_rate=1.25,
                    loudness_rate=0.8,
                    pitch_rate=1.1,
                    enable_subtitle=True,
                    watermark={'enabled': True},
                ),
                parameters={
                    'emotion': 'happy',
                    'speed_ratio': 9,
                    'volume_ratio': 9,
                    'pitch_ratio': 9,
                },
            ),
            provider='volcengine',
        )

        request = transport.requests[0]
        body = json.loads(request.content)
        self.assertEqual(request.headers['authorization'], 'Bearer;speech-token')
        self.assertEqual(body['app']['appid'], 'speech-app')
        self.assertEqual(body['app']['cluster'], 'volcano_tts')
        self.assertEqual(body['audio']['voice_type'], 'voice-one')
        self.assertEqual(body['audio']['encoding'], 'mp3')
        self.assertEqual(body['audio']['rate'], 24000)
        self.assertEqual(body['audio']['emotion'], 'happy')
        self.assertEqual(body['audio']['speed_ratio'], 1.25)
        self.assertEqual(body['audio']['volume_ratio'], 0.8)
        self.assertEqual(body['audio']['pitch_ratio'], 1.1)
        self.assertEqual(body['watermark'], {'enabled': True})
        self.assertEqual(result.output.audio_base64, 'BASE64_AUDIO')
        self.assertEqual(result.output.duration_ms, 1200)
        self.assertEqual(result.data['_response_headers']['x-tt-logid'], 'log-1')

    def test_aliyun_tts_maps_common_rates_and_typed_values_win(self):
        response = {'output': {'audio': {'url': 'https://out/audio.wav'}}}
        transport = RecordingTransport([(200, response)])
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace'))
        self.addCleanup(client.close)
        result = media.speech.synthesize(
            TextToSpeechRequest(
                text='Hello',
                model='qwen-audio-3.0-tts-flash',
                voice='longanhuan',
                language='en',
                audio_config=AudioConfig(
                    format='wav',
                    sample_rate=24000,
                    speech_rate=1.2,
                    loudness_rate=1.5,
                    pitch_rate=0.75,
                ),
                parameters={
                    'instruction': 'Speak warmly.',
                    'rate': 9,
                    'volume': 9,
                    'pitch': 9,
                },
            ),
            provider='aliyun',
        )
        body = json.loads(transport.requests[0].content)
        self.assertEqual(transport.requests[0].url.path, '/api/v1/services/audio/tts/SpeechSynthesizer')
        self.assertEqual(body['model'], 'qwen-audio-3.0-tts-flash')
        self.assertEqual(body['input']['voice'], 'longanhuan')
        self.assertEqual(body['input']['instruction'], 'Speak warmly.')
        self.assertEqual(body['input']['rate'], 1.2)
        self.assertEqual(body['input']['volume'], 75)
        self.assertEqual(body['input']['pitch'], 0.75)
        self.assertEqual(result.output.urls, ['https://out/audio.wav'])

    def test_aliyun_rejects_unsupported_audio_option_before_request(self):
        transport = RecordingTransport([])
        media, client = make_client(
            transport, aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace')
        )
        self.addCleanup(client.close)
        with self.assertRaises(UnsupportedCapabilityError):
            media.speech.synthesize(
                TextToSpeechRequest(
                    text='Hello',
                    model='tts',
                    voice='voice',
                    audio_config=AudioConfig(enable_subtitle=True),
                ),
                provider='aliyun',
            )
        self.assertEqual(len(transport.requests), 0)

    def test_hifly_async_audio_and_task_output(self):
        transport = RecordingTransport(
            [
                (200, {'code': 0, 'task_id': 'audio-task'}),
                (200, {'code': 0, 'status': 3, 'audio_url': 'https://out/audio.mp3', 'duration': 2.5}),
            ]
        )
        media, client = make_client(transport, hifly=HiFlyConfig(token='hifly-token'))
        self.addCleanup(client.close)
        submitted = media.speech.synthesize(
            TextToSpeechRequest(
                text='文案',
                model='hifly-tts-v2',
                voice='voice-1',
                title='音频',
                audio_config=AudioConfig(watermark={'aigc_flag': 1}),
            ),
            provider='hifly',
        )
        self.assertEqual(submitted.status, ModelStatus.QUEUED)
        self.assertIsNone(submitted.output)
        body = json.loads(transport.requests[0].content)
        self.assertEqual(body['voice'], 'voice-1')
        self.assertEqual(body['aigc_flag'], 1)
        completed = media.task.get(submitted.task_ref)
        self.assertIsInstance(completed.output, AudioOutput)
        self.assertEqual(completed.output.urls, ['https://out/audio.mp3'])
        self.assertEqual(completed.output.duration_ms, 2500)

    def test_hifly_rejects_unsupported_audio_config(self):
        media, client = make_client(RecordingTransport([]), hifly=HiFlyConfig(token='token'))
        self.addCleanup(client.close)
        with self.assertRaisesRegex(UnsupportedCapabilityError, 'sample_rate'):
            media.speech.synthesize(
                TextToSpeechRequest(
                    text='text', model='hifly-tts-v2', voice='voice', audio_config=AudioConfig(sample_rate=24000)
                ),
                provider='hifly',
            )

    def test_translate_to_speech_sync_and_async(self):
        sync_transport = RecordingTransport(
            [
                (200, {'choices': [{'message': {'content': 'Hello'}}]}),
                (200, {'output': {'audio': {'url': 'https://out/hello.wav'}}}),
            ]
        )
        media, client = make_client(
            sync_transport,
            deepseek=DeepSeekConfig(api_key='deep-key'),
            aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace'),
        )
        self.addCleanup(client.close)
        request = TranslateToSpeechRequest(
            text='你好',
            source_language='Chinese',
            target_language='English',
            translation_model='deepseek-model',
            speech_model='qwen-tts',
            voice='voice',
        )
        result = media.workflow.translate_to_speech(
            request, text_provider='deepseek', speech_provider='aliyun'
        )
        speech_body = json.loads(sync_transport.requests[1].content)
        self.assertEqual(speech_body['input']['text'], 'Hello')
        self.assertEqual(result.operation, ModelOperation.TRANSLATE_TO_SPEECH)
        self.assertEqual(result.provider, ModelProvider.ALIYUN)
        self.assertEqual(result.output.urls, ['https://out/hello.wav'])
        self.assertEqual(set(result.data), {'translation', 'speech'})

        async_transport = RecordingTransport(
            [
                (200, {'choices': [{'message': {'content': 'Hello'}}]}),
                (200, {'code': 0, 'task_id': 'translated-audio'}),
                (200, {'code': 0, 'status': 3, 'audio_url': 'https://out/translated.mp3'}),
            ]
        )
        media, client = make_client(
            async_transport,
            deepseek=DeepSeekConfig(api_key='deep-key'),
            hifly=HiFlyConfig(token='hifly-token'),
        )
        self.addCleanup(client.close)
        submitted = media.workflow.translate_to_speech(
            request, text_provider='deepseek', speech_provider='hifly'
        )
        self.assertEqual(submitted.task_ref.operation, ModelOperation.TRANSLATE_TO_SPEECH)
        restored = TaskRef.from_json(submitted.task_ref.to_json())
        completed = media.task.get(restored)
        self.assertEqual(completed.operation, ModelOperation.TRANSLATE_TO_SPEECH)
        self.assertEqual(completed.output.urls, ['https://out/translated.mp3'])

    def test_translate_to_speech_preflight_failures_make_no_requests(self):
        request = TranslateToSpeechRequest(
            text='你好',
            target_language='English',
            translation_model='deepseek-model',
            speech_model='tts-model',
            voice='voice',
        )
        cases = [
            (
                'unconfigured',
                {'deepseek': DeepSeekConfig(api_key='deep-key')},
                'aliyun',
                request,
                ConfigurationError,
            ),
            (
                'unsupported',
                {'deepseek': DeepSeekConfig(api_key='deep-key')},
                'deepseek',
                request,
                UnsupportedCapabilityError,
            ),
            (
                'missing speech configuration',
                {
                    'deepseek': DeepSeekConfig(api_key='deep-key'),
                    'volcengine': VolcengineConfig(ark_api_key='ark-key'),
                },
                'volcengine',
                request,
                ConfigurationError,
            ),
            (
                'hifly unsupported option',
                {'deepseek': DeepSeekConfig(api_key='deep-key'), 'hifly': HiFlyConfig(token='token')},
                'hifly',
                request.model_copy(update={'audio_config': AudioConfig(speech_rate=1.1)}),
                UnsupportedCapabilityError,
            ),
            (
                'aliyun unsupported option',
                {
                    'deepseek': DeepSeekConfig(api_key='deep-key'),
                    'aliyun': AliyunConfig(api_key='ali-key', workspace_id='workspace'),
                },
                'aliyun',
                request.model_copy(update={'audio_config': AudioConfig(watermark={'enabled': True})}),
                UnsupportedCapabilityError,
            ),
        ]
        for name, configs, speech_provider, case_request, error_type in cases:
            with self.subTest(name=name):
                transport = RecordingTransport([])
                media, client = make_client(transport, **configs)
                try:
                    with self.assertRaises(error_type):
                        media.workflow.translate_to_speech(
                            case_request,
                            text_provider='deepseek',
                            speech_provider=speech_provider,
                        )
                    self.assertEqual(len(transport.requests), 0)
                finally:
                    client.close()

    def test_translation_failure_does_not_submit_tts(self):
        transport = RecordingTransport([(500, {'message': 'translation unavailable'})])
        media, client = make_client(
            transport,
            deepseek=DeepSeekConfig(api_key='deep-key'),
            hifly=HiFlyConfig(token='hifly-token'),
        )
        self.addCleanup(client.close)
        request = TranslateToSpeechRequest(
            text='你好',
            target_language='English',
            translation_model='deepseek-model',
            speech_model='hifly-tts-v2',
            voice='voice',
        )
        with self.assertRaises(ProviderAPIError):
            media.workflow.translate_to_speech(
                request, text_provider='deepseek', speech_provider='hifly'
            )
        self.assertEqual(len(transport.requests), 1)

    def test_speech_failure_mentions_completed_translation_billing(self):
        transport = RecordingTransport(
            [
                (200, {'choices': [{'message': {'content': 'Hello'}}]}),
                (500, {'message': 'speech unavailable'}),
            ]
        )
        media, client = make_client(
            transport,
            deepseek=DeepSeekConfig(api_key='deep-key'),
            aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace'),
        )
        self.addCleanup(client.close)
        request = TranslateToSpeechRequest(
            text='你好',
            target_language='English',
            translation_model='deepseek-model',
            speech_model='qwen-tts',
            voice='voice',
        )
        with self.assertRaisesRegex(ProviderAPIError, 'translation request may already have been billed'):
            media.workflow.translate_to_speech(
                request, text_provider='deepseek', speech_provider='aliyun'
            )
        self.assertEqual(len(transport.requests), 2)


class MediaTests(unittest.TestCase):
    def test_volcengine_image_and_video_statuses(self):
        responses = [(200, {'data': [{'url': 'https://out/image.png'}]}), (200, {'id': 'video-1'})]
        for status in ('queued', 'running', 'succeeded', 'failed', 'expired', 'cancelled'):
            response = {'id': 'video-1', 'status': status}
            if status == 'succeeded':
                response['content'] = {'video_url': 'https://out/video.mp4'}
            responses.append((200, response))
        transport = RecordingTransport(responses)
        media, client = make_client(transport, volcengine=VolcengineConfig(ark_api_key='ark-key'))
        self.addCleanup(client.close)

        image = media.image.generate(
            ImageGenerationRequest(prompt='cat', model='image-model'), provider='volcengine'
        )
        self.assertEqual(image.output.urls, ['https://out/image.png'])
        self.assertEqual(image.operation, ModelOperation.TEXT_TO_IMAGE)
        submitted = media.video.from_image(
            ImageToVideoRequest(image='data:image/png;base64,AA', prompt='move'), provider='volcengine'
        )
        self.assertIsNone(submitted.output)
        results = [media.task.get(submitted.task_ref) for _ in range(6)]
        self.assertEqual(
            [item.status for item in results],
            [
                ModelStatus.QUEUED,
                ModelStatus.PROCESSING,
                ModelStatus.SUCCEEDED,
                ModelStatus.FAILED,
                ModelStatus.EXPIRED,
                ModelStatus.CANCELED,
            ],
        )
        self.assertEqual(results[2].output.urls, ['https://out/video.mp4'])
        self.assertIsNone(results[3].output)

    def test_volcengine_digital_human_validation_and_generation(self):
        visual = FakeVisualService()
        with patch(
            'openapi.providers.media_generation.adapters.volcengine.create_visual_service',
            return_value=visual,
        ):
            media, client = make_client(
                RecordingTransport([]),
                volcengine=VolcengineConfig(access_key='ak', secret_key='sk'),
            )
            self.addCleanup(client.close)
            validation = media.avatar.validate_image('https://in/person.jpg', provider='volcengine')
            submitted = media.avatar.render(
                DigitalHumanRequest(
                    image_url='https://in/person.jpg',
                    audio_url='https://in/audio.mp3',
                    model='omni-model',
                ),
                provider='volcengine',
            )
            completed = media.task.get(submitted.task_ref)
        self.assertIsInstance(validation.output, ImageValidationOutput)
        self.assertTrue(validation.output.passed)
        self.assertEqual(validation.output.details['face'], 'ok')
        self.assertEqual(visual.ak, 'ak')
        self.assertEqual(completed.output.urls, ['https://out/omni.mp4'])

    def test_aliyun_image_video_validation_and_persisted_task(self):
        transport = RecordingTransport(
            [
                (200, {'output': {'choices': [{'message': {'content': [{'image': 'https://out/image.png'}]}}]}}),
                (200, {'output': {'task_id': 'video-1', 'task_status': 'PENDING'}}),
                (200, {'output': {'check_pass': True, 'humanoid': True}}),
                (200, {'output': {'task_status': 'SUCCEEDED', 'video_url': 'https://out/video.mp4'}}),
            ]
        )
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace'))
        self.addCleanup(client.close)
        image = media.image.edit(
            ImageGenerationRequest(prompt='restyle', images=['data:image/png;base64,AA']), provider='aliyun'
        )
        video = media.video.from_image(ImageToVideoRequest(image='https://in/image.png'), provider='aliyun')
        validation = media.avatar.validate_image('https://in/person.jpg', provider='aliyun')
        restored = TaskRef.from_json(video.task_ref.to_json())
        completed = media.task.get(restored)
        self.assertEqual(image.output.urls, ['https://out/image.png'])
        self.assertTrue(validation.output.passed)
        self.assertEqual(completed.output.urls, ['https://out/video.mp4'])

    def test_aliyun_image_validation_uses_only_boolean_result_fields(self):
        cases = [
            ({'check_pass': True}, True, None),
            ({'check_pass': False, 'humanoid': True}, False, None),
            ({'passed': True}, True, None),
            ({'humanoid': True}, None, ProviderAPIError),
            ({'check_pass': 1}, None, ProviderAPIError),
            ({'passed': 'yes'}, None, ProviderAPIError),
        ]
        for output, expected, error_type in cases:
            with self.subTest(output=output):
                transport = RecordingTransport([(200, {'output': output})])
                media, client = make_client(
                    transport, aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace')
                )
                try:
                    if error_type is not None:
                        with self.assertRaises(error_type):
                            media.avatar.validate_image('https://in/person.jpg', provider='aliyun')
                    else:
                        result = media.avatar.validate_image('https://in/person.jpg', provider='aliyun')
                        self.assertEqual(result.output.passed, expected)
                finally:
                    client.close()

    def test_hifly_avatar_list_clone_and_digital_human(self):
        transport = RecordingTransport(
            [
                (200, {'code': 0, 'data': [{'avatar': 'public-1'}]}),
                (200, {'code': 0, 'data': [{'avatar': 'private-1'}]}),
                (200, {'code': 0, 'task_id': 'clone-1'}),
                (200, {'code': 0, 'task_id': 'video-1'}),
                (200, {'code': 0, 'status': 3, 'avatar': 'avatar-1', 'demo_url': 'https://out/a.mp4'}),
                (200, {'code': 0, 'status': 3, 'video_Url': 'https://out/video.mp4'}),
            ]
        )
        media, client = make_client(transport, hifly=HiFlyConfig(token='token'))
        self.addCleanup(client.close)
        avatars = media.avatar.list(provider='hifly')
        custom_page = media.avatar.list(provider='hifly', page=3, size=7)
        clone = media.avatar.clone(
            AvatarCloneRequest(title='avatar', image_url='https://in/person.jpg'), provider='hifly'
        )
        video = media.avatar.render(
            DigitalHumanRequest(avatar='avatar-1', text='hello', voice='voice-1'), provider='hifly'
        )
        cloned = media.task.get(clone.task_ref)
        completed = media.task.get(video.task_ref)
        self.assertIsInstance(avatars.output, AvatarListOutput)
        self.assertEqual(avatars.output.items[0]['avatar'], 'public-1')
        self.assertEqual((avatars.output.page, avatars.output.size), (1, 20))
        self.assertEqual(custom_page.output.items[0]['avatar'], 'private-1')
        self.assertEqual((custom_page.output.page, custom_page.output.size), (3, 7))
        self.assertEqual(dict(transport.requests[0].url.params), {'page': '1', 'size': '20', 'kind': '2'})
        self.assertEqual(dict(transport.requests[1].url.params), {'page': '3', 'size': '7', 'kind': '2'})
        self.assertEqual(cloned.output.avatar_id, 'avatar-1')
        self.assertEqual(completed.output.urls, ['https://out/video.mp4'])

    def test_hifly_avatar_list_rejects_invalid_pagination_without_request(self):
        transport = RecordingTransport([])
        media, client = make_client(transport, hifly=HiFlyConfig(token='token'))
        self.addCleanup(client.close)
        for kwargs in ({'page': 0}, {'page': -1}, {'page': True}, {'page': 1.5}, {'size': 0}, {'size': '20'}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, 'positive integer'):
                media.avatar.list(provider='hifly', **kwargs)
        self.assertEqual(len(transport.requests), 0)


class ReliabilityTests(unittest.TestCase):
    def test_query_retries_but_submission_does_not(self):
        query_transport = RecordingTransport(
            [
                (429, {'message': 'busy'}),
                (501, {'message': 'busy'}),
                (503, {'message': 'busy'}),
                (200, {'output': {'task_status': 'SUCCEEDED', 'video_url': 'https://out/video.mp4'}}),
            ]
        )
        media, client = make_client(query_transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        result = media.task.get(
            TaskRef(provider='aliyun', operation='digital_human', task_id='task', model='wan')
        )
        self.assertEqual(result.status, ModelStatus.SUCCEEDED)
        self.assertEqual(len(query_transport.requests), 4)

        submit_transport = RecordingTransport([(500, {'message': 'temporary'})])
        media, client = make_client(submit_transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError):
            media.video.from_image(ImageToVideoRequest(image='https://in/image.jpg'), provider='aliyun')
        self.assertEqual(len(submit_transport.requests), 1)

    def test_query_retries_network_errors_and_redacts_exhausted_error(self):
        recovering = RecordingTransport(
            [
                ('connect_error', 'connection failed'),
                ('read_timeout', 'read timed out'),
                (200, {'output': {'task_status': 'SUCCEEDED', 'video_url': 'https://out/video.mp4'}}),
            ]
        )
        media, client = make_client(recovering, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        result = media.task.get(TaskRef(provider='aliyun', operation='digital_human', task_id='task'))
        self.assertEqual(result.output.urls, ['https://out/video.mp4'])
        self.assertEqual(len(recovering.requests), 3)

        exhausted = RecordingTransport([('connect_error', 'ali-secret unavailable')] * 4)
        media, client = make_client(
            exhausted, aliyun=AliyunConfig(api_key='ali-secret', workspace_id='workspace')
        )
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError) as raised:
            media.task.get(TaskRef(provider='aliyun', operation='digital_human', task_id='task'))
        self.assertEqual(len(exhausted.requests), 4)
        self.assertNotIn('ali-secret', str(raised.exception))
        self.assertIn('**********', str(raised.exception))

        submission = RecordingTransport([('connect_error', 'connection failed')])
        media, client = make_client(
            submission, aliyun=AliyunConfig(api_key='key', workspace_id='workspace')
        )
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError):
            media.video.from_image(ImageToVideoRequest(image='https://in/image.jpg'), provider='aliyun')
        self.assertEqual(len(submission.requests), 1)

    def test_wait_timeout_and_terminal_result(self):
        timeout_transport = RecordingTransport([(200, {'output': {'task_status': 'RUNNING'}})])
        media, client = make_client(timeout_transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        with self.assertRaisesRegex(GenerationTimeoutError, 'not cancelled'):
            media.task.wait(
                TaskRef(provider='aliyun', operation='digital_human', task_id='task'),
                timeout=0,
                poll_interval=1,
            )

        terminal_transport = RecordingTransport(
            [
                (200, {'output': {'task_status': 'RUNNING'}}),
                (200, {'output': {'task_status': 'SUCCEEDED', 'video_url': 'https://out/video.mp4'}}),
            ]
        )
        media, client = make_client(terminal_transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        result = media.task.wait(
            TaskRef(provider='aliyun', operation='digital_human', task_id='task'),
            timeout=10,
            poll_interval=1,
        )
        self.assertEqual(result.output.urls, ['https://out/video.mp4'])

    def test_errors_redact_credentials_and_unconfigured_provider_is_clear(self):
        transport = RecordingTransport([(400, {'message': 'invalid deep-secret'})])
        media, client = make_client(transport, deepseek=DeepSeekConfig(api_key='deep-secret'))
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError) as raised:
            media.text.optimize(TextOptimizationRequest(text='text', model='model'), provider='deepseek')
        self.assertNotIn('deep-secret', str(raised.exception))
        self.assertIn('**********', str(raised.exception))

        media, client = make_client(RecordingTransport([]))
        self.addCleanup(client.close)
        with self.assertRaisesRegex(ConfigurationError, 'aliyun.*not configured'):
            media.image.generate(ImageGenerationRequest(prompt='cat'), provider='aliyun')


if __name__ == '__main__':
    unittest.main()
