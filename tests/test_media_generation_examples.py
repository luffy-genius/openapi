import base64
import importlib
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from examples.media_generation import common
from examples.media_generation.workflows import digital_human_from_scratch as digital_human_workflow
from openapi.providers.media_generation import (
    AudioOutput,
    AvatarCloneRequest,
    DigitalHumanRequest,
    FileUploadRequest,
    GenerationTimeoutError,
    ImageGenerationRequest,
    ImageToVideoRequest,
    MediaOutput,
    ModelProvider,
    ModelResult,
    TaskRef,
    TextOptimizationRequest,
    TextOutput,
    TextToSpeechRequest,
    TranslateToSpeechRequest,
)


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.environ = patch.dict(os.environ, {}, clear=True)
        self.environ.start()
        self.addCleanup(self.environ.stop)

    def test_string_and_integer_parsing(self):
        os.environ.update({'STRING': ' value ', 'INTEGER': '12'})
        self.assertEqual(common.env_string('STRING'), 'value')
        self.assertEqual(common.env_integer('INTEGER', minimum=1), 12)

    def test_invalid_values_report_variable_name_without_value(self):
        invalid_secret = 'do-not-print-this-value'
        os.environ['INTEGER'] = invalid_secret
        with self.assertRaisesRegex(common.ExampleError, 'INTEGER must be an integer') as raised:
            common.env_integer('INTEGER')
        self.assertNotIn(invalid_secret, str(raised.exception))

    def test_missing_required_variable_only_names_the_variable(self):
        os.environ['UNRELATED_SECRET'] = 'secret-value'
        with self.assertRaisesRegex(common.ExampleError, 'MISSING') as raised:
            common.env_string('MISSING', required=True)
        self.assertNotIn('secret-value', str(raised.exception))

    def test_capability_level_provider_configs_require_only_relevant_credentials(self):
        os.environ['MEDIA_VOLCENGINE_ARK_API_KEY'] = 'ark-key'
        image = common.provider_config(ModelProvider.VOLCENGINE, 'image')
        self.assertIsNotNone(image.ark_api_key)
        self.assertIsNone(image.speech)
        self.assertIsNone(image.access_key)

        os.environ.clear()
        os.environ.update(
            {
                'MEDIA_VOLCENGINE_SPEECH_APP_ID': 'app-id',
                'MEDIA_VOLCENGINE_SPEECH_ACCESS_TOKEN': 'speech-token',
            }
        )
        speech = common.provider_config(ModelProvider.VOLCENGINE, 'speech')
        self.assertIsNotNone(speech.speech)
        self.assertIsNone(speech.ark_api_key)
        self.assertIsNone(speech.access_key)

        os.environ.clear()
        os.environ['MEDIA_ALIYUN_API_KEY'] = 'aliyun-key'
        validation = common.provider_config(ModelProvider.ALIYUN, 'image_validation')
        self.assertIsNone(validation.workspace_id)
        with self.assertRaisesRegex(common.ExampleError, 'MEDIA_ALIYUN_WORKSPACE_ID'):
            common.provider_config(ModelProvider.ALIYUN, 'image')

    def test_hifly_clone_requires_exactly_one_source(self):
        module = importlib.import_module('examples.media_generation.hifly.clone_avatar')
        for image_url, video_url in ((None, None), ('https://assets.example/a.png', 'https://assets.example/a.mp4')):
            with (
                self.subTest(image_url=image_url, video_url=video_url),
                patch.object(module, 'IMAGE_URL', image_url),
                patch.object(module, 'VIDEO_URL', video_url),
                self.assertRaisesRegex(common.ExampleError, 'exactly one'),
            ):
                module.execute()

    def test_hifly_digital_human_prefers_audio_url(self):
        module = importlib.import_module('examples.media_generation.hifly.digital_human')
        os.environ['MEDIA_HIFLY_AVATAR_ID'] = 'avatar-1'
        media = MagicMock()
        manager = MagicMock()
        manager.__enter__.return_value = media
        with (
            patch.object(module, 'AUDIO_URL', 'https://assets.example/speech.mp3'),
            patch.object(common, 'media_client', return_value=manager),
            patch.object(common, 'complete_result'),
        ):
            module.execute()
        request = media.avatar.render.call_args.args[0]
        self.assertEqual(request.audio_url, 'https://assets.example/speech.mp3')
        self.assertIsNone(request.text)
        self.assertIsNone(request.voice)

    def test_text_request_uses_script_input_and_environment_model(self):
        module = importlib.import_module('examples.media_generation.deepseek.text_optimization')
        os.environ.update({'MEDIA_DEEPSEEK_MODEL': 'model', 'MEDIA_TEXT': 'environment text'})
        media = MagicMock()
        manager = MagicMock()
        manager.__enter__.return_value = media
        with (
            patch.object(module, 'TEXT', 'source text'),
            patch.object(common, 'media_client', return_value=manager),
            patch.object(common, 'complete_result'),
        ):
            module.execute()
        request = media.text.optimize.call_args.args[0]
        self.assertEqual(request.text, 'source text')
        self.assertEqual(request.model, 'model')


class ResultHandlingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.environ = patch.dict(
            os.environ,
            {
                'MEDIA_OUTPUT_DIR': self.temp_dir.name,
                'MEDIA_TASK_TIMEOUT': '10',
                'MEDIA_POLL_INTERVAL': '2',
            },
            clear=True,
        )
        self.environ.start()
        self.addCleanup(self.environ.stop)

    def test_sync_success_prints_summary_without_raw_data(self):
        result = ModelResult[TextOutput](
            provider='deepseek',
            operation='text_optimization',
            status='succeeded',
            output=TextOutput(text='润色结果'),
            data={'secret': 'raw-provider-response'},
        )
        output = io.StringIO()
        with redirect_stdout(output):
            returned = common.complete_result(MagicMock(), result)
        self.assertIs(returned, result)
        self.assertIn('text: 润色结果', output.getvalue())
        self.assertNotIn('raw-provider-response', output.getvalue())

    def test_async_success_saves_task_ref_then_waits(self):
        task_ref = TaskRef(provider='aliyun', operation='image_to_video', task_id='task-1', model='video')
        queued = ModelResult[MediaOutput](
            provider='aliyun', operation='image_to_video', status='queued', task_ref=task_ref
        )
        succeeded = ModelResult[MediaOutput](
            provider='aliyun',
            operation='image_to_video',
            status='succeeded',
            task_ref=task_ref,
            output=MediaOutput(urls=['https://output.example/video.mp4']),
        )
        media = MagicMock()
        media.task.wait.return_value = succeeded

        common.complete_result(media, queued)

        media.task.wait.assert_called_once_with(task_ref, timeout=10, poll_interval=2)
        saved = Path(self.temp_dir.name) / 'aliyun-image_to_video-task-1.json'
        self.assertEqual(TaskRef.from_json(saved.read_text()), task_ref)

    def test_async_timeout_keeps_task_ref_for_recovery(self):
        task_ref = TaskRef(provider='hifly', operation='digital_human', task_id='task-2')
        queued = ModelResult[MediaOutput](
            provider='hifly', operation='digital_human', status='processing', task_ref=task_ref
        )
        media = MagicMock()
        media.task.wait.side_effect = GenerationTimeoutError('timed out; remote task was not cancelled')

        with self.assertRaisesRegex(common.ExampleError, 'resume with MEDIA_TASK_REF'):
            common.complete_result(media, queued)

        saved = Path(self.temp_dir.name) / 'hifly-digital_human-task-2.json'
        self.assertTrue(saved.is_file())

    def test_failed_terminal_result_raises(self):
        result = ModelResult[MediaOutput](
            provider='aliyun',
            operation='image_to_video',
            status='failed',
            error_code='BadInput',
            error_message='invalid image',
        )
        with self.assertRaisesRegex(common.ExampleError, 'status failed'):
            common.complete_result(MagicMock(), result)

    def test_base64_audio_is_decoded_without_printing_payload(self):
        encoded = base64.b64encode(b'wave-data').decode()
        result = ModelResult[AudioOutput](
            provider='volcengine',
            operation='text_to_speech',
            status='succeeded',
            output=AudioOutput(audio_base64=encoded, format='wav'),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            common.complete_result(MagicMock(), result)
        audio_path = Path(self.temp_dir.name) / 'volcengine-text_to_speech-result.wav'
        self.assertEqual(audio_path.read_bytes(), b'wave-data')
        self.assertNotIn(encoded, output.getvalue())

    def test_run_returns_nonzero_and_uses_stderr(self):
        error = io.StringIO()
        with redirect_stderr(error):
            status = common.run(lambda: (_ for _ in ()).throw(common.ExampleError('bad input')))
        self.assertEqual(status, 1)
        self.assertIn('error: bad input', error.getvalue())

    def test_task_ref_can_be_loaded_from_json_or_file(self):
        task_ref = TaskRef(provider='aliyun', operation='image_to_video', task_id='task-3')
        os.environ['MEDIA_TASK_REF'] = task_ref.to_json()
        self.assertEqual(common.load_task_ref(), task_ref)

        path = Path(self.temp_dir.name) / 'task.json'
        path.write_text(task_ref.to_json(), encoding='utf-8')
        os.environ['MEDIA_TASK_REF'] = str(path)
        self.assertEqual(common.load_task_ref(), task_ref)


class ScriptDispatchTests(unittest.TestCase):
    ENVIRONMENT = {
        'MEDIA_DEEPSEEK_MODEL': 'deepseek-model',
        'MEDIA_ALIYUN_TEXT_MODEL': 'aliyun-text',
        'MEDIA_ALIYUN_SPEECH_MODEL': 'aliyun-speech',
        'MEDIA_ALIYUN_SPEECH_VOICE': 'aliyun-voice',
        'MEDIA_ALIYUN_IMAGE_MODEL': 'aliyun-image',
        'MEDIA_ALIYUN_VIDEO_MODEL': 'aliyun-video',
        'MEDIA_ALIYUN_DIGITAL_HUMAN_MODEL': 'aliyun-avatar',
        'MEDIA_VOLCENGINE_TEXT_MODEL': 'volc-text',
        'MEDIA_VOLCENGINE_SPEECH_MODEL': 'volc-speech',
        'MEDIA_VOLCENGINE_SPEECH_VOICE': 'volc-voice',
        'MEDIA_VOLCENGINE_IMAGE_MODEL': 'volc-image',
        'MEDIA_VOLCENGINE_VIDEO_MODEL': 'volc-video',
        'MEDIA_VOLCENGINE_DIGITAL_HUMAN_MODEL': 'volc-avatar',
        'MEDIA_HIFLY_SPEECH_MODEL': 'hifly-speech',
        'MEDIA_HIFLY_SPEECH_VOICE': 'hifly-voice',
        'MEDIA_HIFLY_AVATAR_ID': 'avatar-1',
        'MEDIA_HIFLY_DIGITAL_HUMAN_MODEL': 'hifly-avatar',
        'MEDIA_SILICONFLOW_MODEL': 'sf-speech',
    }

    CASES = (
        (
            'deepseek.text_optimization',
            'text.optimize',
            TextOptimizationRequest,
            ModelProvider.DEEPSEEK,
            {'model': 'deepseek-model', 'text': '这是一段待润色的测试文案。'},
        ),
        (
            'aliyun.text_optimization',
            'text.optimize',
            TextOptimizationRequest,
            ModelProvider.ALIYUN,
            {'model': 'aliyun-text', 'text': '这是一段待润色的测试文案。'},
        ),
        (
            'aliyun.text_to_speech',
            'speech.synthesize',
            TextToSpeechRequest,
            ModelProvider.ALIYUN,
            {'model': 'aliyun-speech', 'voice': 'aliyun-voice'},
        ),
        (
            'aliyun.text_to_image',
            'image.generate',
            ImageGenerationRequest,
            ModelProvider.ALIYUN,
            {'model': 'aliyun-image', 'images': []},
        ),
        (
            'aliyun.image_to_image',
            'image.edit',
            ImageGenerationRequest,
            ModelProvider.ALIYUN,
            {'model': 'aliyun-image', 'images': ['https://cdn.example.com/source.png']},
        ),
        (
            'aliyun.image_to_video',
            'video.from_image',
            ImageToVideoRequest,
            ModelProvider.ALIYUN,
            {'model': 'aliyun-video', 'image': 'https://cdn.example.com/source.png'},
        ),
        (
            'aliyun.digital_human',
            'avatar.render',
            DigitalHumanRequest,
            ModelProvider.ALIYUN,
            {'model': 'aliyun-avatar', 'audio_url': 'https://cdn.example.com/speech.mp3'},
        ),
        (
            'volcengine.text_optimization',
            'text.optimize',
            TextOptimizationRequest,
            ModelProvider.VOLCENGINE,
            {'model': 'volc-text', 'text': '这是一段待润色的测试文案。'},
        ),
        (
            'volcengine.text_to_speech',
            'speech.synthesize',
            TextToSpeechRequest,
            ModelProvider.VOLCENGINE,
            {'model': 'volc-speech', 'voice': 'volc-voice'},
        ),
        (
            'volcengine.text_to_image',
            'image.generate',
            ImageGenerationRequest,
            ModelProvider.VOLCENGINE,
            {'model': 'volc-image', 'images': []},
        ),
        (
            'volcengine.image_to_image',
            'image.edit',
            ImageGenerationRequest,
            ModelProvider.VOLCENGINE,
            {'model': 'volc-image', 'images': ['https://cdn.example.com/source.png']},
        ),
        (
            'volcengine.image_to_video',
            'video.from_image',
            ImageToVideoRequest,
            ModelProvider.VOLCENGINE,
            {'model': 'volc-video', 'image': 'https://cdn.example.com/source.png'},
        ),
        (
            'volcengine.omnihuman',
            'avatar.render',
            DigitalHumanRequest,
            ModelProvider.VOLCENGINE,
            {'model': 'volc-avatar', 'image_url': 'https://cdn.example.com/person.png'},
        ),
        (
            'hifly.text_to_speech',
            'speech.synthesize',
            TextToSpeechRequest,
            ModelProvider.HIFLY,
            {'model': 'hifly-speech', 'voice': 'hifly-voice'},
        ),
        (
            'hifly.clone_avatar',
            'avatar.clone',
            AvatarCloneRequest,
            ModelProvider.HIFLY,
            {'image_url': 'https://cdn.example.com/avatar.png', 'video_url': None},
        ),
        (
            'hifly.digital_human',
            'avatar.render',
            DigitalHumanRequest,
            ModelProvider.HIFLY,
            {'model': 'hifly-avatar', 'avatar': 'avatar-1'},
        ),
        (
            'siliconflow.text_to_speech',
            'speech.synthesize',
            TextToSpeechRequest,
            ModelProvider.SILICONFLOW,
            {'model': 'sf-speech', 'voice': ''},
        ),
    )

    def setUp(self):
        self.environ = patch.dict(os.environ, self.ENVIRONMENT, clear=True)
        self.environ.start()
        self.addCleanup(self.environ.stop)

    @staticmethod
    def _method(media, path):
        value = media
        for name in path.split('.'):
            value = getattr(value, name)
        return value

    def test_capability_scripts_dispatch_typed_request_to_expected_provider(self):
        for module_name, method_path, request_type, provider, expected_fields in self.CASES:
            with self.subTest(module=module_name):
                module = importlib.import_module(f'examples.media_generation.{module_name}')
                media = MagicMock()
                method = self._method(media, method_path)
                result = object()
                method.return_value = result
                manager = MagicMock()
                manager.__enter__.return_value = media
                with (
                    patch.object(common, 'media_client', return_value=manager) as create,
                    patch.object(common, 'complete_result', return_value=result) as complete,
                ):
                    self.assertIs(module.execute(), result)
                create.assert_called_once()
                request = method.call_args.args[0]
                self.assertIsInstance(request, request_type)
                for field, expected in expected_fields.items():
                    self.assertEqual(getattr(request, field), expected)
                self.assertEqual(method.call_args.kwargs['provider'], provider)
                complete.assert_called_once_with(media, result)

    def test_validation_scripts_dispatch_image_and_provider(self):
        for provider_name, provider in (
            ('aliyun', ModelProvider.ALIYUN),
            ('volcengine', ModelProvider.VOLCENGINE),
        ):
            with self.subTest(provider=provider_name):
                module = importlib.import_module(
                    f'examples.media_generation.{provider_name}.validate_digital_human_image'
                )
                media = MagicMock()
                result = object()
                media.avatar.validate_image.return_value = result
                manager = MagicMock()
                manager.__enter__.return_value = media
                with (
                    patch.object(common, 'media_client', return_value=manager),
                    patch.object(common, 'complete_result', return_value=result),
                ):
                    module.execute()
                media.avatar.validate_image.assert_called_once_with(module.IMAGE_URL, provider=provider)

    def test_hifly_avatar_list_dispatches_pagination(self):
        module = importlib.import_module('examples.media_generation.hifly.list_avatars')
        media = MagicMock()
        manager = MagicMock()
        manager.__enter__.return_value = media
        with (
            patch.object(common, 'media_client', return_value=manager),
            patch.object(common, 'complete_result'),
        ):
            module.execute()
        media.avatar.list.assert_called_once_with(provider=ModelProvider.HIFLY, page=1, size=20)

    def test_workflow_dispatches_deepseek_and_selected_speech_provider(self):
        module = importlib.import_module('examples.media_generation.workflows.translate_to_speech')
        os.environ['MEDIA_WORKFLOW_SPEECH_PROVIDER'] = 'aliyun'
        media = MagicMock()
        result = object()
        media.workflow.translate_to_speech.return_value = result
        manager = MagicMock()
        manager.__enter__.return_value = media
        with (
            patch.object(common, 'workflow_client', return_value=manager) as create,
            patch.object(common, 'complete_result', return_value=result),
        ):
            module.execute()
        create.assert_called_once_with(ModelProvider.ALIYUN)
        request = media.workflow.translate_to_speech.call_args.args[0]
        self.assertIsInstance(request, TranslateToSpeechRequest)
        self.assertEqual(media.workflow.translate_to_speech.call_args.kwargs['text_provider'], ModelProvider.DEEPSEEK)
        self.assertEqual(media.workflow.translate_to_speech.call_args.kwargs['speech_provider'], ModelProvider.ALIYUN)

    def test_resume_script_queries_saved_reference_before_waiting(self):
        module = importlib.import_module('examples.media_generation.resume_task')
        task_ref = TaskRef(provider='aliyun', operation='image_to_video', task_id='resume-1')
        result = ModelResult[MediaOutput](
            provider='aliyun', operation='image_to_video', status='processing', task_ref=task_ref
        )
        media = MagicMock()
        media.task.get.return_value = result
        manager = MagicMock()
        manager.__enter__.return_value = media
        with (
            patch.object(common, 'load_task_ref', return_value=task_ref),
            patch.object(common, 'provider_config', return_value=object()),
            patch.object(module.MediaClient, 'create', return_value=manager),
            patch.object(common, 'complete_result', return_value=result) as complete,
        ):
            module.execute()
        media.task.get.assert_called_once_with(task_ref)
        complete.assert_called_once_with(media, result)


class DigitalHumanWorkflowTests(unittest.TestCase):
    @staticmethod
    def _base_sources():
        return dict(
            avatar_image_url=None,
            avatar_image_path=None,
            avatar_video_url=None,
            avatar_video_path=None,
            voice_audio_url=None,
            voice_audio_path=None,
            avatar_title='形象',
            voice_title='音色',
            digital_human_title='视频',
            digital_human_text='大家好',
            aigc_flag=None,
            language='zh',
            avatar_clone_model=None,
            parameters={},
        )

    @staticmethod
    def _media():
        media = MagicMock()
        upload = MagicMock()
        upload.output.file_id = 'file-1'
        media.avatar.upload.return_value = upload
        return media

    @staticmethod
    def _results():
        clone_final = MagicMock()
        clone_final.output.avatar_id = 'avatar-1'
        voice_final = MagicMock()
        voice_final.output.voice_id = 'voice-1'
        render_final = MagicMock()
        render_final.output.urls = ['https://out/video.mp4']
        return [clone_final, voice_final, render_final]

    def _run(self, media, results, **source_overrides):
        sources = self._base_sources()
        sources.update(source_overrides)
        with patch.object(common, 'complete_result', side_effect=results):
            with redirect_stdout(io.StringIO()):
                return digital_human_workflow.run(media, **sources)

    def test_url_image_and_audio_sources(self):
        media = self._media()
        results = self._results()
        returned = self._run(
            media,
            results,
            avatar_image_url='https://cdn.example.com/photo.jpg',
            voice_audio_url='https://cdn.example.com/sample.wav',
        )
        self.assertIs(returned, results[2])

        avatar_request = media.avatar.clone.call_args.args[0]
        self.assertIsInstance(avatar_request, AvatarCloneRequest)
        self.assertEqual(avatar_request.image_url, 'https://cdn.example.com/photo.jpg')
        self.assertIsNone(avatar_request.image_file_id)
        self.assertIsNone(avatar_request.video_url)
        self.assertIsNone(avatar_request.video_file_id)
        media.avatar.upload.assert_not_called()

        voice_request = media.speech.clone_voice.call_args.args[0]
        self.assertEqual(voice_request.audio_url, 'https://cdn.example.com/sample.wav')

        render_request = media.avatar.render.call_args.args[0]
        self.assertEqual(render_request.avatar, 'avatar-1')
        self.assertEqual(render_request.voice, 'voice-1')
        self.assertIsNone(render_request.resolution)
        self.assertIsNone(render_request.ratio)

    def test_local_image_source_uploads_and_clones_with_image_file_id(self):
        media = self._media()
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / 'photo.jpg'
            image_path.write_bytes(b'jpeg-data')
            self._run(
                media,
                self._results(),
                avatar_image_path=str(image_path),
                voice_audio_url='https://cdn.example.com/sample.wav',
            )
        upload_request = media.avatar.upload.call_args.args[0]
        self.assertIsInstance(upload_request, FileUploadRequest)
        self.assertEqual(upload_request.content, b'jpeg-data')
        self.assertEqual(upload_request.file_extension, 'jpg')
        self.assertEqual(upload_request.content_type, 'image/jpeg')
        avatar_request = media.avatar.clone.call_args.args[0]
        self.assertEqual(avatar_request.image_file_id, 'file-1')
        self.assertIsNone(avatar_request.image_url)

    def test_local_video_source_uploads_and_clones_with_video_file_id(self):
        media = self._media()
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / 'source.mp4'
            video_path.write_bytes(b'mp4-data')
            self._run(
                media,
                self._results(),
                avatar_video_path=str(video_path),
                voice_audio_url='https://cdn.example.com/sample.wav',
            )
        upload_request = media.avatar.upload.call_args.args[0]
        self.assertEqual(upload_request.content_type, 'video/mp4')
        self.assertEqual(upload_request.file_extension, 'mp4')
        avatar_request = media.avatar.clone.call_args.args[0]
        self.assertEqual(avatar_request.video_file_id, 'file-1')
        self.assertIsNone(avatar_request.video_url)

    def test_local_audio_source_clones_voice_with_file_id(self):
        media = self._media()
        with tempfile.TemporaryDirectory() as directory:
            audio_path = Path(directory) / 'sample.wav'
            audio_path.write_bytes(b'wav-data')
            self._run(
                media,
                self._results(),
                avatar_image_url='https://cdn.example.com/photo.jpg',
                voice_audio_path=str(audio_path),
            )
        upload_request = media.avatar.upload.call_args.args[0]
        self.assertEqual(upload_request.content_type, 'audio/wav')
        voice_request = media.speech.clone_voice.call_args.args[0]
        self.assertEqual(voice_request.file_id, 'file-1')
        self.assertIsNone(voice_request.audio_url)

    def test_empty_output_raises_explicit_error(self):
        media = self._media()
        results = self._results()
        results[2].output.urls = []
        with self.assertRaisesRegex(common.ExampleError, 'without output media'):
            self._run(
                media,
                results,
                avatar_image_url='https://cdn.example.com/photo.jpg',
                voice_audio_url='https://cdn.example.com/sample.wav',
            )


if __name__ == '__main__':
    unittest.main()
