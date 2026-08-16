import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from openapi.providers.storages import (
    ObjectMetadata,
    ObjectNotFoundError,
    ObjectStorageClient,
    ObjectStorageConfigurationError,
    ObjectStorageError,
)
from openapi.providers.storages.aliyun_oss import (
    Client,
    OSSConfig,
    OSSConfigurationError,
    OSSObjectNotFoundError,
    OSSProviderError,
)


class SDKError(Exception):
    def __init__(self, message='SDK error', *, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


class DownloadResponse(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.was_closed = False

    def close(self):
        self.was_closed = True
        super().close()


class FailingReadResponse(DownloadResponse):
    def read(self, size=-1):
        raise SDKError('remote stream failure', status=503)


class FakeBucket:
    instances = []

    def __init__(self, auth, endpoint, bucket_name, *, region):
        self.auth = auth
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.region = region
        self.calls = []
        self.responses = {}
        self.__class__.instances.append(self)

    def _response(self, name, default=None):
        value = self.responses.get(name, default)
        if isinstance(value, Exception):
            raise value
        return value

    def put_object(self, key, content, headers=None):
        self.calls.append(('put_object', key, content, headers))
        return self._response('put_object')

    def get_object(self, key):
        self.calls.append(('get_object', key))
        return self._response('get_object')

    def delete_object(self, key):
        self.calls.append(('delete_object', key))
        return self._response('delete_object')

    def object_exists(self, key):
        self.calls.append(('object_exists', key))
        return self._response('object_exists', False)

    def head_object(self, key):
        self.calls.append(('head_object', key))
        return self._response('head_object')

    def list_objects_v2(self, **kwargs):
        self.calls.append(('list_objects_v2', kwargs))
        responses = self.responses['list_objects_v2']
        value = responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def sign_url(self, method, key, expires, *, slash_safe):
        self.calls.append(('sign_url', method, key, expires, slash_safe))
        return self._response(
            'sign_url',
            f'https://{self.bucket_name}.{self.endpoint.removeprefix("https://")}/{key}?signature=yes',
        )


class FakeCredentialsProvider:
    def __init__(self, access_key_id, access_key_secret):
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret


class FakeAuth:
    def __init__(self, credentials):
        self.credentials = credentials


def fake_sdk():
    FakeBucket.instances = []
    return SimpleNamespace(
        credentials=SimpleNamespace(StaticCredentialsProvider=FakeCredentialsProvider),
        ProviderAuthV4=FakeAuth,
        Bucket=FakeBucket,
    )


def make_config(**overrides):
    values = {
        'access_key_id': 'access-key',
        'access_key_secret': 'secret-key',
        'endpoint': 'oss-cn-hangzhou-internal.aliyuncs.com',
        'region': 'cn-hangzhou',
        'bucket_name': 'media-bucket',
    }
    values.update(overrides)
    return OSSConfig(**values)


class ConfigTests(unittest.TestCase):
    def test_required_values_expiry_and_secret_masking(self):
        for field in ('access_key_id', 'access_key_secret', 'endpoint', 'region', 'bucket_name'):
            values = make_config().model_dump()
            values.pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                OSSConfig(**values)
        with self.assertRaises(ValidationError):
            make_config(sign_expires=0)

        config = make_config()
        self.assertNotIn('access-key', repr(config))
        self.assertNotIn('secret-key', config.model_dump_json())
        self.assertIn('**********', config.model_dump_json())

    def test_missing_extra_has_actionable_error(self):
        missing = ModuleNotFoundError("No module named 'oss2'", name='oss2')
        with patch('openapi.providers.storages.aliyun_oss.importlib.import_module', side_effect=missing):
            with self.assertRaisesRegex(OSSConfigurationError, r"pip install 'openapipy\[aliyun-oss\]'"):
                Client(make_config())

    def test_import_failures_raise_configuration_errors(self):
        other = ModuleNotFoundError("No module named 'requests'", name='requests')
        with patch('openapi.providers.storages.aliyun_oss.importlib.import_module', side_effect=other):
            with self.assertRaisesRegex(OSSConfigurationError, 'Failed to import'):
                Client(make_config())
        with patch('openapi.providers.storages.aliyun_oss.importlib.import_module', side_effect=RuntimeError('boom')):
            with self.assertRaisesRegex(OSSConfigurationError, 'Failed to import'):
                Client(make_config())

    def test_config_rejects_invalid_optional_and_endpoint_values(self):
        for overrides in (
            {'public_endpoint': '  '},
            {'public_base_url': ' '},
            {'sign_expires': -5},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                make_config(**overrides)
        for endpoint in ('https://user:pass@oss.example.com', 'https://oss.example.com/?x=1'):
            with self.subTest(endpoint=endpoint), self.assertRaises(OSSConfigurationError):
                Client(make_config(endpoint=endpoint))


class ClientTests(unittest.TestCase):
    def setUp(self):
        sdk = fake_sdk()
        patcher = patch('openapi.providers.storages.aliyun_oss.importlib.import_module', return_value=sdk)
        self.addCleanup(patcher.stop)
        patcher.start()
        self.client = Client(make_config())
        self.internal_bucket, self.public_bucket = FakeBucket.instances

    def test_client_satisfies_shared_object_storage_interface(self):
        self.assertIsInstance(self.client, ObjectStorageClient)
        self.assertTrue(issubclass(OSSProviderError, ObjectStorageError))
        self.assertTrue(issubclass(OSSConfigurationError, ObjectStorageConfigurationError))
        self.assertTrue(issubclass(OSSObjectNotFoundError, ObjectNotFoundError))

    def test_uses_v4_auth_region_and_internal_and_derived_public_endpoints(self):
        self.assertIsInstance(self.internal_bucket.auth, FakeAuth)
        credentials = self.internal_bucket.auth.credentials
        self.assertEqual((credentials.access_key_id, credentials.access_key_secret), ('access-key', 'secret-key'))
        self.assertEqual(self.internal_bucket.endpoint, 'https://oss-cn-hangzhou-internal.aliyuncs.com')
        self.assertEqual(self.public_bucket.endpoint, 'https://oss-cn-hangzhou.aliyuncs.com')
        self.assertEqual(self.internal_bucket.region, 'cn-hangzhou')
        self.assertEqual(self.public_bucket.region, 'cn-hangzhou')

    def test_explicit_public_endpoint_is_used_for_public_bucket(self):
        FakeBucket.instances = []
        client = Client(make_config(public_endpoint='http://oss-cn-shanghai.aliyuncs.com'))
        self.assertIsNotNone(client)
        self.assertEqual(FakeBucket.instances[1].endpoint, 'http://oss-cn-shanghai.aliyuncs.com')

    def test_put_object_forwards_headers_and_returns_key(self):
        key = self.client.put_object('images/猫 photo.jpg', b'content', headers={'Content-Type': 'image/jpeg'})
        self.assertEqual(
            self.internal_bucket.calls,
            [('put_object', 'images/猫 photo.jpg', b'content', {'Content-Type': 'image/jpeg'})],
        )
        self.assertEqual(
            key,
            'images/猫 photo.jpg',
        )

    def test_download_streams_to_file_and_closes_remote_response(self):
        response = DownloadResponse(b'chunked content')
        self.internal_bucket.responses['get_object'] = response
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'nested.bin'
            self.client.download_to('nested.bin', destination)
            self.assertEqual(destination.read_bytes(), b'chunked content')
        self.assertTrue(response.was_closed)

    def test_download_accepts_an_open_binary_destination_without_closing_it(self):
        response = DownloadResponse(b'in-memory content')
        self.internal_bucket.responses['get_object'] = response
        destination = io.BytesIO()
        self.client.download_to('memory.bin', destination)
        self.assertEqual(destination.getvalue(), b'in-memory content')
        self.assertFalse(destination.closed)
        self.assertTrue(response.was_closed)

    def test_download_local_io_failure_is_not_a_provider_error(self):
        response = DownloadResponse(b'content')
        self.internal_bucket.responses['get_object'] = response
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / 'missing' / 'out.bin'
            with self.assertRaises(OSError) as caught:
                self.client.download_to('nested.bin', missing)
        self.assertIsInstance(caught.exception, FileNotFoundError)
        self.assertTrue(response.was_closed)

    def test_download_stream_failure_is_a_provider_error(self):
        response = FailingReadResponse(b'partial')
        self.internal_bucket.responses['get_object'] = response
        destination = io.BytesIO()
        with self.assertRaises(OSSProviderError):
            self.client.download_to('stream.bin', destination)
        self.assertTrue(response.was_closed)

    def test_exists_delete_and_errors_are_normalised(self):
        self.internal_bucket.responses['object_exists'] = True
        self.assertTrue(self.client.exists('present'))

        self.internal_bucket.responses['object_exists'] = SDKError(status=404)
        self.assertFalse(self.client.exists('missing'))
        self.internal_bucket.responses['delete_object'] = SDKError(code='NoSuchKey')
        self.client.delete_object('missing')

        original = SDKError(status=404)
        self.internal_bucket.responses['head_object'] = original
        with self.assertRaises(OSSObjectNotFoundError) as caught:
            self.client.stat('missing')
        self.assertIs(caught.exception.__cause__, original)

        original = SDKError(status=503)
        self.internal_bucket.responses['put_object'] = original
        with self.assertRaises(OSSProviderError) as caught:
            self.client.put_object('failed', b'content')
        self.assertNotIsInstance(caught.exception, OSSObjectNotFoundError)
        self.assertIs(caught.exception.__cause__, original)

    def test_stat_returns_normalised_metadata(self):
        self.internal_bucket.responses['head_object'] = SimpleNamespace(
            content_length=12,
            last_modified=1_700_000_000,
            etag='etag-one',
            content_type='image/png',
        )
        metadata = self.client.stat('asset.png')
        self.assertIsInstance(metadata, ObjectMetadata)
        self.assertEqual(metadata.key, 'asset.png')
        self.assertEqual(metadata.size, 12)
        self.assertEqual(metadata.last_modified, datetime.fromtimestamp(1_700_000_000, tz=timezone.utc))
        self.assertEqual(metadata.etag, 'etag-one')
        self.assertEqual(metadata.content_type, 'image/png')

    def test_iter_objects_consumes_all_list_objects_v2_pages(self):
        first = SimpleNamespace(key='a.txt', size=1, last_modified='2026-01-01T00:00:00Z', etag='a')
        second = SimpleNamespace(key='b.txt', size=2, last_modified=1_700_000_000, etag='b')
        self.internal_bucket.responses['list_objects_v2'] = [
            SimpleNamespace(object_list=[first], is_truncated=True, next_continuation_token='page-2'),
            SimpleNamespace(object_list=[second], is_truncated=False, next_continuation_token=''),
        ]
        objects = list(self.client.iter_objects(prefix='docs/', delimiter='/'))
        self.assertEqual([item.key for item in objects], ['a.txt', 'b.txt'])
        self.assertEqual([item.size for item in objects], [1, 2])
        self.assertEqual(objects[0].last_modified, datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertIsNone(objects[0].content_type)
        self.assertEqual(
            self.internal_bucket.calls,
            [
                ('list_objects_v2', {'prefix': 'docs/', 'delimiter': '/', 'continuation_token': ''}),
                ('list_objects_v2', {'prefix': 'docs/', 'delimiter': '/', 'continuation_token': 'page-2'}),
            ],
        )

    def test_delete_on_remote_failure_raises_provider_error(self):
        original = SDKError(status=503)
        self.internal_bucket.responses['delete_object'] = original
        with self.assertRaises(OSSProviderError) as caught:
            self.client.delete_object('failed')
        self.assertIs(caught.exception.__cause__, original)

    def test_object_url_uses_derived_bucket_endpoint(self):
        self.assertEqual(
            self.client.object_url('folder/a b.txt'),
            'https://media-bucket.oss-cn-hangzhou.aliyuncs.com/folder/a%20b.txt',
        )

    def test_iter_objects_continues_past_empty_truncated_pages(self):
        item = SimpleNamespace(key='b.txt', size=2, last_modified=1_700_000_000, etag='b')
        self.internal_bucket.responses['list_objects_v2'] = [
            SimpleNamespace(object_list=[], is_truncated=True, next_continuation_token='page-2'),
            SimpleNamespace(object_list=[item], is_truncated=False, next_continuation_token=''),
        ]
        objects = list(self.client.iter_objects())
        self.assertEqual([item.key for item in objects], ['b.txt'])
        self.assertEqual(
            [call[1]['continuation_token'] for call in self.internal_bucket.calls],
            ['', 'page-2'],
        )

    def test_iter_objects_rejects_invalid_continuation_tokens(self):
        cases = [
            [SimpleNamespace(object_list=[], is_truncated=True, next_continuation_token='')],
            [
                SimpleNamespace(object_list=[], is_truncated=True, next_continuation_token='page-2'),
                SimpleNamespace(object_list=[], is_truncated=True, next_continuation_token='page-2'),
            ],
        ]
        for pages in cases:
            with self.subTest(pages=pages):
                self.internal_bucket.responses['list_objects_v2'] = pages
                with self.assertRaises(OSSProviderError):
                    list(self.client.iter_objects())

    def test_normalise_datetime_variants(self):
        from openapi.providers.storages.aliyun_oss import _normalise_datetime

        self.assertIsNone(_normalise_datetime(None))
        self.assertEqual(
            _normalise_datetime('Wed, 01 Jan 2026 00:00:00 GMT'),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(
            _normalise_datetime(1_700_000_000), datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
        )
        with self.assertRaises(TypeError):
            _normalise_datetime(b'not-a-date')

    def test_url_encoding_cdn_parsing_signed_url_and_external_rejection(self):
        FakeBucket.instances = []
        client = Client(make_config(public_base_url='https://cdn.example.com/assets/'))
        key = '资料/hello world+1.txt'
        url = client.object_url(key)
        self.assertEqual(
            url,
            'https://cdn.example.com/assets/%E8%B5%84%E6%96%99/hello%20world%2B1.txt',
        )
        self.assertEqual(client.key_from_url(f'{url}?x-oss-signature=expired'), key)
        self.assertIsNone(client.key_from_url('https://external.example.com/assets/file.txt'))
        self.assertIsNone(client.key_from_url('https://cdn.example.com/other/file.txt'))

        oss_url = 'https://media-bucket.oss-cn-hangzhou.aliyuncs.com/folder/a%20b.txt?expired=true'
        self.assertEqual(client.key_from_url(oss_url), 'folder/a b.txt')

    def test_sign_url_uses_public_bucket_defaults_and_overrides(self):
        signed = self.client.sign_url('folder/a b.txt')
        self.assertIn('signature=yes', signed)
        self.assertEqual(
            self.public_bucket.calls,
            [('sign_url', 'GET', 'folder/a b.txt', 3600, True)],
        )
        self.client.sign_url('upload.bin', method='put', expires=60)
        self.assertEqual(self.public_bucket.calls[-1], ('sign_url', 'PUT', 'upload.bin', 60, True))
        with self.assertRaises(OSSConfigurationError):
            self.client.sign_url('bad', expires=0)

    def test_sign_url_rejects_empty_method(self):
        for method in (None, '', '  '):
            with self.subTest(method=method), self.assertRaises(OSSConfigurationError):
                self.client.sign_url('folder/a b.txt', method=method)


class PackagingTests(unittest.TestCase):
    def test_wheel_contains_optional_extras_and_modules(self):
        import subprocess
        import sys
        import zipfile

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    '-m',
                    'pip',
                    'wheel',
                    '--no-deps',
                    '--no-build-isolation',
                    '--wheel-dir',
                    directory,
                    str(repo_root),
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            wheels = list(Path(directory).glob('openapipy-*.whl'))
            self.assertEqual(len(wheels), 1)
            with zipfile.ZipFile(wheels[0]) as archive:
                names = archive.namelist()
                metadata_name = next(name for name in names if name.endswith('.dist-info/METADATA'))
                metadata = archive.read(metadata_name).decode()
                self.assertIn('Provides-Extra: media-generation', metadata)
                self.assertIn('Provides-Extra: aliyun-oss', metadata)
                self.assertIn('openapi/providers/storages/aliyun_oss.py', names)
                self.assertIn('openapi/providers/media_generation/adapters/siliconflow.py', names)
                self.assertFalse(any(name.startswith('examples/') for name in names))


if __name__ == '__main__':
    unittest.main()
