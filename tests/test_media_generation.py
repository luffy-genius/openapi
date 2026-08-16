import base64
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
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
    FileUploadRequest,
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
    ProviderErrorCode,
    SiliconFlowConfig,
    SpeechTranscriptionRequest,
    TaskRef,
    TextOptimizationAction,
    TextOptimizationRequest,
    TextOptimizationStyle,
    TextOutput,
    TextToSpeechRequest,
    TranslateToSpeechRequest,
    UnsupportedCapabilityError,
    VoiceCloneRequest,
    VoiceDesignRequest,
    VolcengineConfig,
    VolcengineSpeechConfig,
    classify_provider_error,
)
from openapi.providers.media_generation.registry import Capability


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
        kwargs = {'content': payload} if isinstance(payload, bytes) else {'json': payload}
        return httpx.Response(status, headers=headers[0] if headers else None, request=request, **kwargs)


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
    def test_media_choice_labels_preserve_wire_values(self):
        self.assertEqual(
            ModelProvider.choices,
            [
                ('volcengine', '火山引擎'),
                ('aliyun', '阿里云百炼'),
                ('hifly', '飞影 HiFly'),
                ('deepseek', 'DeepSeek'),
                ('siliconflow', 'SiliconFlow'),
            ],
        )
        self.assertEqual(
            ModelStatus.choices,
            [
                ('queued', '排队中'),
                ('processing', '处理中'),
                ('succeeded', '已成功'),
                ('failed', '已失败'),
                ('expired', '已过期'),
                ('canceled', '已取消'),
            ],
        )
        self.assertEqual(
            ModelOperation.choices,
            [
                ('text_optimization', '文本优化'),
                ('text_to_speech', '文本转语音'),
                ('speech_to_text', '语音转文字'),
                ('voice_clone', '声音复刻'),
                ('voice_design', '音色设计'),
                ('translate_to_speech', '翻译后转语音'),
                ('text_to_image', '文生图'),
                ('image_to_image', '图生图'),
                ('image_to_video', '图生视频'),
                ('digital_human_image_validation', '数字人图片校验'),
                ('digital_human', '数字人生成'),
                ('avatar_clone', '形象克隆'),
                ('avatar_list', '形象列表'),
                ('voice_list', '声音列表'),
                ('file_upload', '文件上传'),
            ],
        )
        self.assertEqual(
            TextOptimizationAction.choices,
            [
                ('polish', '润色'),
                ('expand', '扩写'),
                ('simplify', '简化'),
                ('translate', '翻译'),
            ],
        )
        self.assertEqual(
            TextOptimizationStyle.choices,
            [
                ('professional', '专业'),
                ('friendly', '友好'),
                ('lively', '生动'),
                ('concise', '简洁'),
            ],
        )
        self.assertEqual(
            Capability.choices,
            [
                ('text', '文本'),
                ('speech', '语音'),
                ('speech transcription', '语音识别'),
                ('voice clone', '声音复刻'),
                ('voice design', '音色设计'),
                ('voice list', '声音列表'),
                ('file upload', '文件上传'),
                ('image', '图片'),
                ('video', '视频'),
                ('image validation', '图片校验'),
                ('digital human', '数字人'),
                ('avatar clone', '形象克隆'),
                ('avatar list', '形象列表'),
                ('task query', '任务查询'),
            ],
        )
        request = TextOptimizationRequest(text='原文', model='model')
        self.assertEqual(request.action.label, '润色')
        self.assertEqual(request.model_dump(mode='json')['action'], 'polish')

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

    def test_media_requests_validate_public_contract_and_protect_typed_fields(self):
        with self.assertRaises(ValidationError):
            ImageGenerationRequest(prompt=' ', n=1)
        with self.assertRaises(ValidationError):
            ImageGenerationRequest(prompt='cat', n=5)
        with self.assertRaisesRegex(ValidationError, 'reserved fields'):
            ImageGenerationRequest(prompt='cat', n=2, parameters={'n': 4})
        with self.assertRaises(ValidationError):
            ImageToVideoRequest(image='https://in/image.png', duration=16)
        with self.assertRaisesRegex(ValidationError, 'reserved fields'):
            ImageToVideoRequest(image='https://in/image.png', parameters={'resolution': '720P'})
        with self.assertRaisesRegex(ValidationError, 'Extra inputs'):
            DigitalHumanRequest(avatar='avatar', unknown_setting=True)

    def test_text_to_speech_reference_validation(self):
        with self.assertRaisesRegex(ValidationError, 'mutually exclusive'):
            TextToSpeechRequest(text='text', model='tts', voice='voice', reference_audio=b'audio')
        with self.assertRaisesRegex(ValidationError, 'reference_text'):
            TextToSpeechRequest(text='text', model='tts', reference_audio=b'audio', reference_text=' ')
        request = TextToSpeechRequest(text='text', model='tts', reference_audio=b'audio', reference_text='原文')
        self.assertEqual(request.voice, '')
        # Neither voice nor reference_audio is fine; providers fall back to default_voice.
        self.assertEqual(TextToSpeechRequest(text='text', model='tts').voice, '')

    def test_avatar_clone_request_sources_and_model_coercion(self):
        for kwargs in (
            {},
            {'image_url': 'u', 'video_url': 'v'},
            {'image_file_id': 'f', 'video_file_id': 'g'},
            {'image_url': 'u', 'image_file_id': 'f'},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValidationError, 'exactly one'):
                AvatarCloneRequest(title='t', **kwargs)
        request = AvatarCloneRequest(image_file_id='file-1', model='3')
        self.assertEqual(request.model, 3)
        self.assertIsNone(AvatarCloneRequest(image_url='https://in/a.jpg').model)

    def test_speech_transcription_file_urls_cap(self):
        request = SpeechTranscriptionRequest(file_urls=['https://in/video.mp4'])
        self.assertEqual(len(request.file_urls), 1)
        with self.assertRaises(ValidationError):
            SpeechTranscriptionRequest(file_urls=['https://in/a.mp4', 'https://in/b.mp4'])

    def test_siliconflow_config_boundaries(self):
        config = SiliconFlowConfig(api_key='key')
        self.assertEqual(config.base_url, 'https://api.siliconflow.cn/v1')
        with self.assertRaisesRegex(ValidationError, 'HTTPS'):
            SiliconFlowConfig(api_key='key', base_url='http://api.example.com')
        for field, value in (('speed', 0.24), ('speed', 4.01), ('gain', -10.01), ('gain', 10.01)):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                SiliconFlowConfig(api_key='key', **{field: value})

    def test_classify_provider_error_normalises_camel_case_and_separators(self):
        cases = {
            'DataInspectionFailed': ProviderErrorCode.CONTENT_REJECTED,
            'InvalidApiKey': ProviderErrorCode.AUTH_FAILED,
            'RateLimitExceeded': ProviderErrorCode.RATE_LIMITED,
            'PermissionDenied': ProviderErrorCode.OWNERSHIP_ERROR,
            'ContentFiltered': ProviderErrorCode.CONTENT_REJECTED,
            'internal-error': ProviderErrorCode.SERVICE_UNAVAILABLE,
        }
        for provider_code, expected in cases.items():
            with self.subTest(provider_code=provider_code):
                classification = classify_provider_error(provider_code=provider_code)
                self.assertEqual(classification.code, expected)

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
    def test_aliyun_transcription_task_and_standardized_text(self):
        transport = RecordingTransport(
            [
                (200, {'output': {'task_id': 'asr-1', 'task_status': 'PENDING'}}),
                (
                    200,
                    {
                        'output': {
                            'task_status': 'SUCCEEDED',
                            'results': [{'transcription_url': 'https://out/transcript.json'}],
                        }
                    },
                ),
                (200, {'transcripts': [{'text': '第一段'}, {'text': '第二段'}]}),
            ]
        )
        media, client = make_client(
            transport,
            aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace', asr_model='paraformer-v2'),
        )
        self.addCleanup(client.close)

        submitted = media.speech.transcribe(
            SpeechTranscriptionRequest(
                file_urls=['https://in/video.mp4'], parameters={'language_hints': ['zh']}
            ),
            provider='aliyun',
        )
        restored = TaskRef.from_json(submitted.task_ref.to_json())
        completed = media.task.get(restored)

        submit = transport.requests[0]
        self.assertEqual(submit.url.host, 'workspace.cn-beijing.maas.aliyuncs.com')
        self.assertEqual(submit.url.path, '/api/v1/services/audio/asr/transcription')
        self.assertEqual(submit.headers['x-dashscope-async'], 'enable')
        submit_body = json.loads(submit.content)
        self.assertEqual(submit_body['model'], 'paraformer-v2')
        self.assertEqual(submit_body['input'], {'file_urls': ['https://in/video.mp4']})
        self.assertEqual(submit_body['parameters'], {'language_hints': ['zh']})
        self.assertEqual(transport.requests[1].url.host, 'workspace.cn-beijing.maas.aliyuncs.com')
        self.assertEqual(transport.requests[1].url.path, '/api/v1/tasks/asr-1')
        self.assertEqual(completed.output.text, '第一段\n第二段')

    def test_aliyun_transcription_download_retries_and_never_falls_back(self):
        retrying = RecordingTransport(
            [
                (200, {'output': {'task_id': 'asr-1', 'task_status': 'PENDING'}}),
                (
                    200,
                    {
                        'output': {
                            'task_status': 'SUCCEEDED',
                            'results': [{'transcription_url': 'https://out/transcript.json'}],
                        }
                    },
                ),
                (503, {'message': 'temporary'}),
                (200, {'transcripts': [{'text': '重试成功'}]}),
            ]
        )
        media, client = make_client(retrying, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        submitted = media.speech.transcribe(
            SpeechTranscriptionRequest(file_urls=['https://in/video.mp4']), provider='aliyun'
        )
        completed = media.task.get(submitted.task_ref)
        self.assertEqual(completed.output.text, '重试成功')
        self.assertEqual(len(retrying.requests), 4)

        exhausted = RecordingTransport(
            [
                (200, {'output': {'task_id': 'asr-2', 'task_status': 'PENDING'}}),
                (
                    200,
                    {
                        'output': {
                            'task_status': 'SUCCEEDED',
                            'results': [{'transcription_url': 'https://out/transcript.json'}],
                        }
                    },
                ),
            ]
            + [(503, {'message': 'temporary'})] * 4
        )
        media, client = make_client(exhausted, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        submitted = media.speech.transcribe(
            SpeechTranscriptionRequest(file_urls=['https://in/video.mp4']), provider='aliyun'
        )
        with self.assertRaises(ProviderAPIError) as raised:
            media.task.get(submitted.task_ref)
        error = raised.exception
        self.assertEqual(error.code, ProviderErrorCode.SERVICE_UNAVAILABLE)
        self.assertFalse(error.fallback_allowed)
        self.assertTrue(error.remote_task_may_exist)
        self.assertEqual(len(exhausted.requests), 6)

    def test_aliyun_voice_clone_and_design_preview(self):
        transport = RecordingTransport(
            [
                (200, {'request_id': 'clone-request', 'output': {'voice_id': 'voice-clone'}}),
                (
                    200,
                    {
                        'request_id': 'design-request',
                        'output': {
                            'voice_id': 'voice-design',
                            'target_model': 'cosyvoice-v3.5-plus',
                            'preview_audio': {'data': 'UklGRg==', 'response_format': 'wav'},
                        },
                    },
                ),
            ]
        )
        media, client = make_client(
            transport,
            aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace'),
        )
        self.addCleanup(client.close)

        cloned = media.speech.clone_voice(
            VoiceCloneRequest(audio_url='https://in/sample.wav', prefix='用户 123', language='zh'),
            provider='aliyun',
        )
        designed = media.speech.design_voice(
            VoiceDesignRequest(
                prompt='温暖的女声',
                preview_text='你好',
                prefix='preview',
                target_model='cosyvoice-v3.5-plus',
            ),
            provider='aliyun',
        )

        clone_body = json.loads(transport.requests[0].content)
        design_body = json.loads(transport.requests[1].content)
        self.assertEqual(clone_body['input']['prefix'], '123')
        self.assertEqual(cloned.output.voice_id, 'voice-clone')
        self.assertEqual(cloned.output.request_id, 'clone-request')
        self.assertEqual(design_body['parameters'], {'sample_rate': 24000, 'response_format': 'wav'})
        self.assertEqual(designed.output.model, 'cosyvoice-v3.5-plus')
        self.assertEqual(designed.output.preview_audio.audio_base64, 'UklGRg==')

    def test_siliconflow_reference_audio_and_binary_speech(self):
        transport = RecordingTransport([(200, b'ID3-audio', {'content-type': 'audio/mpeg'})])
        media, client = make_client(transport, siliconflow=SiliconFlowConfig(api_key='sf-secret'))
        self.addCleanup(client.close)

        result = media.speech.synthesize(
            TextToSpeechRequest(
                text='待合成文本',
                model='FunAudioLLM/CosyVoice2-0.5B',
                reference_audio=b'RIFF-reference',
                reference_content_type='audio/wav',
                reference_text='参考文本',
            ),
            provider='siliconflow',
        )

        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(str(transport.requests[0].url), 'https://api.siliconflow.cn/v1/audio/speech')
        self.assertNotIn(b'sf-secret', transport.requests[0].content)
        speech_body = json.loads(transport.requests[0].content)
        self.assertEqual(speech_body['model'], 'FunAudioLLM/CosyVoice2-0.5B')
        self.assertEqual(speech_body['input'], '待合成文本')
        self.assertIs(speech_body['stream'], False)
        self.assertNotIn('voice', speech_body)
        self.assertEqual(speech_body['references'][0]['text'], '参考文本')
        expected_audio = f'data:audio/wav;base64,{base64.b64encode(b"RIFF-reference").decode()}'
        self.assertEqual(speech_body['references'][0]['audio'], expected_audio)
        self.assertEqual(base64.b64decode(result.output.audio_base64), b'ID3-audio')
        self.assertEqual(result.output.format, 'mpeg')

    def test_siliconflow_downloads_audio_url_response(self):
        transport = RecordingTransport(
            [
                (200, {'data': {'url': 'https://audio.example.test/result.wav'}}),
                (200, b'RIFF-audio', {'content-type': 'audio/wav'}),
            ]
        )
        media, client = make_client(
            transport,
            siliconflow=SiliconFlowConfig(
                api_key='sf-secret',
                base_url='https://tts.example.test/v1',
                default_voice='voice-1',
            ),
        )
        self.addCleanup(client.close)

        result = media.speech.synthesize(
            TextToSpeechRequest(text='hello', model='speech-model'),
            provider='siliconflow',
        )

        speech_body = json.loads(transport.requests[0].content)
        self.assertEqual(str(transport.requests[0].url), 'https://tts.example.test/v1/audio/speech')
        self.assertEqual(speech_body['voice'], 'voice-1')
        self.assertIs(speech_body['stream'], False)
        self.assertEqual(result.output.urls, ['https://audio.example.test/result.wav'])
        self.assertEqual(base64.b64decode(result.output.audio_base64), b'RIFF-audio')
        self.assertEqual(str(transport.requests[1].url), 'https://audio.example.test/result.wav')

    def test_siliconflow_rejects_invalid_speech_options_before_request(self):
        for kwargs in (
            {'response_format': 'flac'},
            {'response_format': 'ogg'},
            {'sample_rate': 12000},
        ):
            with self.subTest(kwargs=kwargs):
                transport = RecordingTransport([])
                media, client = make_client(transport, siliconflow=SiliconFlowConfig(api_key='key', **kwargs))
                self.addCleanup(client.close)
                with self.assertRaisesRegex(ValueError, 'response_format|sample_rate'):
                    media.speech.synthesize(
                        TextToSpeechRequest(text='text', model='model', voice='voice'),
                        provider='siliconflow',
                    )
                self.assertEqual(len(transport.requests), 0)

    def test_siliconflow_sample_rate_format_combos(self):
        for kwargs in (
            {'response_format': 'opus'},  # default sample_rate 44100 is not valid for opus
            {'response_format': 'mp3', 'sample_rate': 48000},
        ):
            with self.subTest(kwargs=kwargs):
                transport = RecordingTransport([])
                media, client = make_client(transport, siliconflow=SiliconFlowConfig(api_key='key', **kwargs))
                self.addCleanup(client.close)
                with self.assertRaisesRegex(ValueError, 'not supported for response_format'):
                    media.speech.synthesize(
                        TextToSpeechRequest(text='text', model='model', voice='voice'),
                        provider='siliconflow',
                    )
                self.assertEqual(len(transport.requests), 0)

        for kwargs in (
            {'response_format': 'mp3', 'sample_rate': 32000},
            {'response_format': 'opus', 'sample_rate': 48000},
        ):
            with self.subTest(kwargs=kwargs):
                transport = RecordingTransport([(200, b'ID3-audio', {'content-type': 'audio/mpeg'})])
                media, client = make_client(transport, siliconflow=SiliconFlowConfig(api_key='key', **kwargs))
                self.addCleanup(client.close)
                result = media.speech.synthesize(
                    TextToSpeechRequest(text='text', model='model', voice='voice'),
                    provider='siliconflow',
                )
                self.assertEqual(result.output.audio_base64, base64.b64encode(b'ID3-audio').decode())

    def test_siliconflow_reference_audio_requires_reference_text(self):
        media, client = make_client(RecordingTransport([]), siliconflow=SiliconFlowConfig(api_key='key'))
        self.addCleanup(client.close)
        with self.assertRaisesRegex(ValueError, 'reference_text'):
            media.speech.synthesize(
                TextToSpeechRequest(text='text', model='model', reference_audio=b'audio'),
                provider='siliconflow',
            )

    def test_other_providers_reject_reference_audio_before_request(self):
        cases = {
            'hifly': HiFlyConfig(token='token'),
            'aliyun': AliyunConfig(api_key='key', workspace_id='workspace'),
            'volcengine': VolcengineConfig(
                speech=VolcengineSpeechConfig(app_id='app', access_token='token')
            ),
        }
        for name, config in cases.items():
            with self.subTest(name=name):
                transport = RecordingTransport([])
                media, client = make_client(transport, **{name: config})
                self.addCleanup(client.close)
                with self.assertRaises(UnsupportedCapabilityError):
                    media.speech.synthesize(
                        TextToSpeechRequest(
                            text='text', model='model', reference_audio=b'audio', reference_text='原文'
                        ),
                        provider=name,
                    )
                self.assertEqual(len(transport.requests), 0)

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
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace'))
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
        result = media.workflow.translate_to_speech(request, text_provider='deepseek', speech_provider='aliyun')
        speech_body = json.loads(sync_transport.requests[1].content)
        self.assertEqual(speech_body['input']['text'], 'Hello')
        self.assertEqual(result.operation, ModelOperation.TRANSLATE_TO_SPEECH)
        self.assertEqual(result.provider, ModelProvider.ALIYUN)
        self.assertEqual(result.output.urls, ['https://out/hello.wav'])
        self.assertEqual(set(result.data), {'translation', 'speech'})
        self.assertIsNone(result.error_kind)
        self.assertIsNone(result.error_code)
        self.assertIsNone(result.error_message)
        self.assertFalse(result.retryable)
        self.assertFalse(result.fallback_allowed)

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
        submitted = media.workflow.translate_to_speech(request, text_provider='deepseek', speech_provider='hifly')
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
            media.workflow.translate_to_speech(request, text_provider='deepseek', speech_provider='hifly')
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
        with self.assertRaisesRegex(ProviderAPIError, 'translation request may already have been billed') as raised:
            media.workflow.translate_to_speech(request, text_provider='deepseek', speech_provider='aliyun')
        self.assertEqual(len(transport.requests), 2)
        error = raised.exception
        self.assertEqual(error.code, ProviderErrorCode.SERVICE_UNAVAILABLE)
        self.assertEqual(error.http_status, 500)
        self.assertTrue(error.retryable)
        self.assertTrue(error.fallback_allowed)
        self.assertFalse(error.remote_task_may_exist)


class MediaTests(unittest.TestCase):
    def test_hifly_upload_voice_list_and_file_id_inputs(self):
        transport = RecordingTransport(
            [
                (
                    200,
                    {
                        'code': 0,
                        'data': {
                            'upload_url': 'https://upload.example.test/file',
                            'file_id': 'file-1',
                            'content_type': 'video/mp4',
                        },
                    },
                ),
                (200, {}),
                (200, {'code': 0, 'data': [{'voice': 'voice-1'}]}),
                (200, {'code': 0, 'data': {'task_id': 'avatar-task'}}),
                (200, {'code': 0, 'data': {'task_id': 'video-task'}}),
                (200, {'code': 0, 'data': {'task_id': 'voice-task'}}),
                (200, {'code': 0, 'data': {'status': 3, 'voice': 'cloned-voice'}}),
            ]
        )
        media, client = make_client(transport, hifly=HiFlyConfig(token='hifly-secret'))
        self.addCleanup(client.close)

        uploaded = media.avatar.upload(
            FileUploadRequest(content=b'video-data', file_extension='.mp4', content_type='video/mp4'),
            provider='hifly',
        )
        voices = media.speech.list_voices(provider='hifly', page=2, size=10)
        avatar = media.avatar.clone(
            AvatarCloneRequest(title='avatar', video_file_id=uploaded.output.file_id), provider='hifly'
        )
        video = media.avatar.render(
            DigitalHumanRequest(avatar='avatar-1', file_id='audio-file'), provider='hifly'
        )
        voice = media.speech.clone_voice(
            VoiceCloneRequest(title='voice', file_id='audio-file', language='zh'), provider='hifly'
        )
        completed = media.task.get(voice.task_ref)

        self.assertEqual(transport.requests[1].method, 'PUT')
        self.assertEqual(transport.requests[1].content, b'video-data')
        self.assertNotIn('authorization', transport.requests[1].headers)
        self.assertEqual(voices.output.items[0]['voice'], 'voice-1')
        self.assertEqual(
            dict(transport.requests[2].url.params), {'page': '2', 'size': '10', 'kind': '1'}
        )
        self.assertEqual(transport.requests[3].url.path, '/api/v2/hifly/avatar/create_by_video')
        self.assertEqual(json.loads(transport.requests[3].content)['file_id'], 'file-1')
        self.assertEqual(json.loads(transport.requests[4].content)['file_id'], 'audio-file')
        self.assertEqual(avatar.task_ref.task_id, 'avatar-task')
        self.assertEqual(video.task_ref.task_id, 'video-task')
        self.assertEqual(completed.output.voice_id, 'cloned-voice')

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

        image = media.image.generate(ImageGenerationRequest(prompt='cat', model='image-model'), provider='volcengine')
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
        video = media.video.from_image(
            ImageToVideoRequest(
                image='https://in/image.png',
                last_image='https://in/last.png',
                prompt='move',
                duration=5,
                resolution='1080P',
                ratio='auto',
                prompt_extend=True,
                watermark=False,
            ),
            provider='aliyun',
        )
        validation = media.avatar.validate_image('https://in/person.jpg', provider='aliyun')
        restored = TaskRef.from_json(video.task_ref.to_json())
        completed = media.task.get(restored)
        self.assertEqual(image.output.urls, ['https://out/image.png'])
        video_body = json.loads(transport.requests[1].content)
        self.assertEqual(
            video_body['parameters'],
            {
                'duration': 5,
                'resolution': '1080P',
                'watermark': False,
                'prompt_extend': True,
            },
        )
        self.assertEqual(video_body['input']['media'][1]['type'], 'last_frame')
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
                media, client = make_client(transport, aliyun=AliyunConfig(api_key='ali-key', workspace_id='workspace'))
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
            DigitalHumanRequest(avatar='avatar-1', text='hello', voice='voice-1'),
            provider='hifly',
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
        render_body = json.loads(transport.requests[3].content)
        self.assertNotIn('resolution', render_body)
        self.assertNotIn('ratio', render_body)
        self.assertEqual(cloned.output.avatar_id, 'avatar-1')
        self.assertEqual(completed.output.urls, ['https://out/video.mp4'])

    def test_hifly_avatar_clone_routes_image_and_video_file_ids(self):
        transport = RecordingTransport(
            [
                (200, {'code': 0, 'task_id': 'image-clone'}),
                (200, {'code': 0, 'task_id': 'video-clone'}),
                (200, {'code': 0, 'task_id': 'video-url-clone'}),
            ]
        )
        media, client = make_client(transport, hifly=HiFlyConfig(token='token'))
        self.addCleanup(client.close)
        media.avatar.clone(AvatarCloneRequest(image_file_id='image-file', model='3'), provider='hifly')
        media.avatar.clone(AvatarCloneRequest(video_file_id='video-file'), provider='hifly')
        media.avatar.clone(AvatarCloneRequest(video_url='https://in/source.mp4'), provider='hifly')

        image_request = transport.requests[0]
        self.assertEqual(image_request.url.path, '/api/v2/hifly/avatar/create_by_image')
        image_body = json.loads(image_request.content)
        self.assertEqual(image_body['file_id'], 'image-file')
        self.assertEqual(image_body['model'], 3)
        video_file_request = transport.requests[1]
        self.assertEqual(video_file_request.url.path, '/api/v2/hifly/avatar/create_by_video')
        self.assertEqual(json.loads(video_file_request.content)['file_id'], 'video-file')
        self.assertEqual(transport.requests[2].url.path, '/api/v2/hifly/avatar/create_by_video')
        self.assertEqual(json.loads(transport.requests[2].content)['video_url'], 'https://in/source.mp4')

    def test_hifly_list_voices_kind_defaults_to_self_cloned(self):
        transport = RecordingTransport(
            [
                (200, {'code': 0, 'data': [{'voice': 'self-1'}]}),
                (200, {'code': 0, 'data': [{'voice': 'public-1'}]}),
            ]
        )
        media, client = make_client(transport, hifly=HiFlyConfig(token='token'))
        self.addCleanup(client.close)
        media.speech.list_voices(provider='hifly')
        media.speech.list_voices(provider='hifly', kind=2)
        self.assertEqual(
            dict(transport.requests[0].url.params), {'page': '1', 'size': '20', 'kind': '1'}
        )
        self.assertEqual(
            dict(transport.requests[1].url.params), {'page': '1', 'size': '20', 'kind': '2'}
        )
        with self.assertRaisesRegex(ValueError, 'positive integer'):
            media.speech.list_voices(provider='hifly', kind=0)

    def test_hifly_digital_human_rejects_resolution_ratio_and_seed(self):
        transport = RecordingTransport([])
        media, client = make_client(transport, hifly=HiFlyConfig(token='token'))
        self.addCleanup(client.close)
        for kwargs in ({'resolution': '720P'}, {'ratio': '16:9'}, {'seed': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(UnsupportedCapabilityError):
                media.avatar.render(
                    DigitalHumanRequest(avatar='avatar-1', text='text', voice='voice', **kwargs),
                    provider='hifly',
                )
        self.assertEqual(len(transport.requests), 0)

    def test_aliyun_image_to_video_rejects_unsupported_options(self):
        transport = RecordingTransport([])
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        cases = (
            (ImageToVideoRequest(image='https://in/image.png', ratio='16:9'), 'auto'),
            (ImageToVideoRequest(image='https://in/image.png', seed=7), 'seed'),
            (ImageToVideoRequest(image='https://in/image.png', negative_prompt='blur'), 'negative_prompt'),
        )
        for request, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(UnsupportedCapabilityError, message):
                media.video.from_image(request, provider='aliyun')
        self.assertEqual(len(transport.requests), 0)

    def test_aliyun_digital_human_rejects_unsupported_resolution_and_ratio(self):
        transport = RecordingTransport([])
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        for kwargs in ({'resolution': '1080P'}, {'ratio': '16:9'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(UnsupportedCapabilityError):
                media.avatar.render(
                    DigitalHumanRequest(
                        image_url='https://in/person.jpg', audio_url='https://in/audio.mp3', **kwargs
                    ),
                    provider='aliyun',
                )
        self.assertEqual(len(transport.requests), 0)

    def test_volcengine_image_to_video_lowercases_resolution(self):
        transport = RecordingTransport([(200, {'id': 'video-1'})])
        media, client = make_client(transport, volcengine=VolcengineConfig(ark_api_key='ark-key'))
        self.addCleanup(client.close)
        media.video.from_image(
            ImageToVideoRequest(image='https://in/image.png', resolution='1080P', ratio='16:9'),
            provider='volcengine',
        )
        body = json.loads(transport.requests[0].content)
        self.assertEqual(body['resolution'], '1080p')
        self.assertEqual(body['ratio'], '16:9')

    def test_volcengine_visual_task_failure_carries_error_fields(self):
        visual = FakeVisualService()

        def failed_query(body):
            visual.calls.append(('query', body))
            return {
                'code': 10000,
                'data': {
                    'status': 'failed',
                    'code': 'RequestDeniedByContentFilter',
                    'message': '内容违规',
                },
            }

        visual.cv_sync2async_get_result = failed_query
        with patch(
            'openapi.providers.media_generation.adapters.volcengine.create_visual_service',
            return_value=visual,
        ):
            media, client = make_client(
                RecordingTransport([]),
                volcengine=VolcengineConfig(access_key='ak', secret_key='sk'),
            )
            self.addCleanup(client.close)
            submitted = media.avatar.render(
                DigitalHumanRequest(
                    image_url='https://in/person.jpg',
                    audio_url='https://in/audio.mp3',
                ),
                provider='volcengine',
            )
            completed = media.task.get(submitted.task_ref)
        self.assertEqual(completed.status, ModelStatus.FAILED)
        self.assertEqual(completed.error_code, 'RequestDeniedByContentFilter')
        self.assertEqual(completed.error_kind, ProviderErrorCode.CONTENT_REJECTED)
        self.assertFalse(completed.retryable)
        self.assertFalse(completed.fallback_allowed)

    def test_hifly_avatar_list_rejects_invalid_pagination_without_request(self):
        transport = RecordingTransport([])
        media, client = make_client(transport, hifly=HiFlyConfig(token='token'))
        self.addCleanup(client.close)
        for kwargs in ({'page': 0}, {'page': -1}, {'page': True}, {'page': 1.5}, {'size': 0}, {'size': '20'}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, 'positive integer'):
                media.avatar.list(provider='hifly', **kwargs)
        self.assertEqual(len(transport.requests), 0)


class MediaDownloadTests(unittest.TestCase):
    def test_download_returns_content_and_type(self):
        transport = RecordingTransport([(200, b'ID3-audio', {'content-type': 'audio/mpeg'})])
        media, client = make_client(transport)
        self.addCleanup(client.close)
        result = media.download('https://cdn.example.com/audio.mp3')
        self.assertEqual(result.content, b'ID3-audio')
        self.assertEqual(result.content_type, 'audio/mpeg')

    def test_download_classifies_http_and_network_errors(self):
        for response, expected_code, expected_status in (
            ((503, {'message': 'busy'}), ProviderErrorCode.SERVICE_UNAVAILABLE, 503),
            ((429, {'message': 'busy'}), ProviderErrorCode.RATE_LIMITED, 429),
        ):
            with self.subTest(status=response[0]):
                media, client = make_client(RecordingTransport([response]))
                try:
                    with self.assertRaises(ProviderAPIError) as raised:
                        media.download('https://cdn.example.com/audio.mp3')
                    error = raised.exception
                    self.assertEqual(error.code, expected_code)
                    self.assertEqual(error.http_status, expected_status)
                    self.assertTrue(error.retryable)
                    self.assertTrue(error.fallback_allowed)
                finally:
                    client.close()

        media, client = make_client(RecordingTransport([('read_timeout', 'timed out')]))
        try:
            with self.assertRaises(ProviderAPIError) as raised:
                media.download('https://cdn.example.com/audio.mp3')
            error = raised.exception
            self.assertEqual(error.code, ProviderErrorCode.TIMEOUT)
            self.assertTrue(error.retryable)
            self.assertTrue(error.fallback_allowed)
        finally:
            client.close()

    def test_download_to_writes_stream_to_file_and_stream(self):
        transport = RecordingTransport([(200, b'ID3-part-one-part-two', {'content-type': 'audio/mpeg'})])
        media, client = make_client(transport)
        self.addCleanup(client.close)
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / 'audio.mp3'
            media.download_to('https://cdn.example.com/audio.mp3', destination)
            self.assertEqual(destination.read_bytes(), b'ID3-part-one-part-two')

        stream_transport = RecordingTransport([(200, b'RIFF-audio', {'content-type': 'audio/wav'})])
        media, client = make_client(stream_transport)
        self.addCleanup(client.close)
        buffer = io.BytesIO()
        media.download_to('https://cdn.example.com/audio.wav', buffer)
        self.assertFalse(buffer.closed)
        self.assertEqual(buffer.getvalue(), b'RIFF-audio')

    def test_download_to_local_io_error_is_not_a_provider_error(self):
        transport = RecordingTransport([(200, b'audio', {'content-type': 'audio/mpeg'})])
        media, client = make_client(transport)
        self.addCleanup(client.close)
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / 'missing-dir' / 'audio.mp3'
            with self.assertRaises(OSError):
                media.download_to('https://cdn.example.com/audio.mp3', missing)


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
        result = media.task.get(TaskRef(provider='aliyun', operation='digital_human', task_id='task', model='wan'))
        self.assertEqual(result.status, ModelStatus.SUCCEEDED)
        self.assertEqual(len(query_transport.requests), 4)

        submit_transport = RecordingTransport([(500, {'message': 'temporary'})])
        media, client = make_client(submit_transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError):
            media.video.from_image(ImageToVideoRequest(image='https://in/image.jpg'), provider='aliyun')
        self.assertEqual(len(submit_transport.requests), 1)

    def test_provider_errors_expose_safe_retry_and_fallback_guidance(self):
        auth_transport = RecordingTransport([(401, {'code': 'Unauthorized', 'message': 'token expired'})])
        media, client = make_client(auth_transport, hifly=HiFlyConfig(token='secret'))
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError) as raised:
            media.avatar.list(provider='hifly')
        error = raised.exception
        self.assertEqual(error.code, ProviderErrorCode.AUTH_FAILED)
        self.assertEqual(error.http_status, 401)
        self.assertTrue(error.fallback_allowed)
        self.assertFalse(error.remote_task_may_exist)

        query_transport = RecordingTransport([(503, {'code': 'InternalError', 'message': 'busy'})] * 4)
        media, client = make_client(
            query_transport,
            aliyun=AliyunConfig(api_key='key', workspace_id='workspace'),
        )
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError) as raised:
            media.task.get(TaskRef(provider='aliyun', operation='digital_human', task_id='task'))
        error = raised.exception
        self.assertEqual(error.code, ProviderErrorCode.SERVICE_UNAVAILABLE)
        self.assertTrue(error.retryable)
        self.assertFalse(error.fallback_allowed)
        self.assertTrue(error.remote_task_may_exist)

    def test_content_rejection_matches_camelcase_code_without_message_markers(self):
        transport = RecordingTransport(
            [
                (
                    200,
                    {
                        'output': {
                            'task_status': 'FAILED',
                            'code': 'DataInspectionFailed',
                            'message': 'request terminated',
                        }
                    },
                ),
            ]
        )
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        result = media.task.get(TaskRef(provider='aliyun', operation='image_to_video', task_id='task'))
        self.assertEqual(result.error_kind, ProviderErrorCode.CONTENT_REJECTED)
        self.assertEqual(result.error_code, 'DataInspectionFailed')
        self.assertFalse(result.retryable)
        self.assertFalse(result.fallback_allowed)

    def test_ambiguous_submission_timeout_does_not_allow_fallback(self):
        transport = RecordingTransport([('read_timeout', 'submission timed out')])
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError) as raised:
            media.video.from_image(ImageToVideoRequest(image='https://in/image.jpg'), provider='aliyun')
        error = raised.exception
        self.assertEqual(error.code, ProviderErrorCode.TIMEOUT)
        self.assertTrue(error.retryable)
        self.assertTrue(error.remote_task_may_exist)
        self.assertFalse(error.fallback_allowed)

    def test_terminal_content_rejection_never_allows_provider_fallback(self):
        transport = RecordingTransport(
            [
                (
                    200,
                    {
                        'output': {
                            'task_status': 'FAILED',
                            'code': 'DataInspectionFailed',
                            'message': 'content safety rejection',
                        }
                    },
                ),
                (
                    200,
                    {
                        'output': {
                            'task_status': 'FAILED',
                            'code': 'InternalError',
                            'message': 'provider overloaded',
                        }
                    },
                ),
            ]
        )
        media, client = make_client(transport, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
        self.addCleanup(client.close)
        task = TaskRef(provider='aliyun', operation='image_to_video', task_id='task')

        rejected = media.task.get(task)
        unavailable = media.task.get(task)

        self.assertEqual(rejected.error_kind, ProviderErrorCode.CONTENT_REJECTED)
        self.assertFalse(rejected.retryable)
        self.assertFalse(rejected.fallback_allowed)
        self.assertEqual(unavailable.error_kind, ProviderErrorCode.SERVICE_UNAVAILABLE)
        self.assertTrue(unavailable.retryable)
        self.assertTrue(unavailable.fallback_allowed)

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
        media, client = make_client(exhausted, aliyun=AliyunConfig(api_key='ali-secret', workspace_id='workspace'))
        self.addCleanup(client.close)
        with self.assertRaises(ProviderAPIError) as raised:
            media.task.get(TaskRef(provider='aliyun', operation='digital_human', task_id='task'))
        self.assertEqual(len(exhausted.requests), 4)
        self.assertNotIn('ali-secret', str(raised.exception))
        self.assertIn('**********', str(raised.exception))

        submission = RecordingTransport([('connect_error', 'connection failed')])
        media, client = make_client(submission, aliyun=AliyunConfig(api_key='key', workspace_id='workspace'))
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
