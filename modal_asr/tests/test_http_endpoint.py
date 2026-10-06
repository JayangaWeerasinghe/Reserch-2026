import asyncio
import importlib.util
import logging
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class FakeImage:
    def apt_install(self, *args):
        return self

    def pip_install(self, *args):
        return self

    def env(self, *args):
        return self


class FakeFastAPI:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def register(handler):
            self.routes[path] = handler
            return handler
        return register


class FakeHTTPException(Exception):
    def __init__(self, status_code, detail, headers=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}


class FakeJSONResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code


class FakeUpload:
    def __init__(self, filename="sample.ogg", content_type="audio/ogg", payload=b"audio"):
        self.filename = filename
        self.content_type = content_type
        self.payload = payload
        self.closed = False

    async def read(self, size=-1):
        return self.payload[:size]

    async def close(self):
        self.closed = True


class FakeRequest:
    def __init__(self, headers=None, form_data=None, form_error=None):
        self.headers = headers or {}
        self.form_data = form_data or {}
        self.form_error = form_error

    async def form(self, **kwargs):
        if self.form_error:
            raise self.form_error
        return self.form_data


class ModalEndpointTests(unittest.TestCase):
    def setUp(self):
        self.fastapi_apps = []
        modal_stub = ModuleType("modal")
        modal_stub.App = lambda *args, **kwargs: SimpleNamespace(
            function=lambda **options: lambda function: function,
            local_entrypoint=lambda **options: lambda function: function,
        )
        modal_stub.Image = SimpleNamespace(debian_slim=lambda **kwargs: FakeImage())
        modal_stub.Volume = SimpleNamespace(from_name=lambda *args, **kwargs: object())
        modal_stub.Secret = SimpleNamespace(from_name=lambda *args, **kwargs: object())
        modal_stub.asgi_app = lambda **kwargs: lambda function: function

        fastapi_stub = ModuleType("fastapi")
        fastapi_stub.FastAPI = lambda: self._new_fastapi()
        fastapi_stub.HTTPException = FakeHTTPException
        fastapi_stub.Request = FakeRequest
        responses_stub = ModuleType("fastapi.responses")
        responses_stub.JSONResponse = FakeJSONResponse

        modules = {
            "modal": modal_stub,
            "fastapi": fastapi_stub,
            "fastapi.responses": responses_stub,
        }
        self.module_name = "modal_asr_app_under_test"
        self.module = None
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location(self.module_name, APP_PATH)
            self.module = importlib.util.module_from_spec(spec)
            sys.modules[self.module_name] = self.module
            spec.loader.exec_module(self.module)
            self.web_app = self.module.listen_app()

        self.handler = self.web_app.routes["/listen"]
        self.upload = FakeUpload()
        self.remote = AsyncMock(return_value={
            "text": "ඩයමන්ඩ් හැඩතියි පුල්ලි තියෙනවා.",
            "model": "caller-cannot-choose-model",
            "language": "si",
            "inference_seconds": 9.354,
        })
        self.module.transcribe_uploaded = SimpleNamespace(remote=SimpleNamespace(aio=self.remote))
        self.environment = patch.dict(os.environ, {self.module.AUTH_ENV_NAME: "test-shared-secret"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(sys.modules.pop, self.module_name, None)

    def _new_fastapi(self):
        application = FakeFastAPI()
        self.fastapi_apps.append(application)
        return application

    def request(self, upload=None, fields=None, headers=None, content_length=None):
        form_data = dict(fields or {})
        if upload is not None:
            form_data["file"] = upload
        request_headers = (
            {"authorization": "Bearer test-shared-secret"}
            if headers is None
            else dict(headers)
        )
        if content_length is not None:
            request_headers["content-length"] = str(content_length)
        return FakeRequest(headers=request_headers, form_data=form_data)

    def invoke(self, request):
        return asyncio.run(self.handler(request))

    def test_adapter_compatible_success_ignores_requested_model(self):
        request = self.request(
            self.upload,
            fields={
                "model": "arbitrary/untrusted-model",
                "language": "si",
                "response_format": "json",
            },
        )
        response = self.invoke(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content["text"], "ඩයමන්ඩ් හැඩතියි පුල්ලි තියෙනවා.")
        self.assertEqual(response.content["model"], "Lingalingeswaran/whisper-small-sinhala")
        self.assertEqual(response.content["language"], "si")
        self.assertEqual(response.content["inference_seconds"], 9.354)
        self.remote.assert_awaited_once_with(file_bytes=b"audio", filename="sample.ogg")
        self.assertTrue(self.upload.closed)

    def test_missing_and_invalid_bearer_auth_return_401(self):
        for auth_header in (None, "Bearer incorrect"):
            headers = {"authorization": auth_header} if auth_header else {}
            with self.subTest(auth_header=bool(auth_header)):
                with self.assertRaises(FakeHTTPException) as raised:
                    self.invoke(self.request(self.upload, headers=headers))
                self.assertEqual(raised.exception.status_code, 401)
        self.remote.assert_not_awaited()

    def test_server_secret_missing_fails_closed(self):
        with patch.dict(os.environ, {self.module.AUTH_ENV_NAME: ""}):
            with self.assertRaises(FakeHTTPException) as raised:
                self.invoke(self.request(self.upload))
        self.assertEqual(raised.exception.status_code, 503)
        self.remote.assert_not_awaited()

    def test_missing_empty_and_unsupported_files_are_rejected(self):
        cases = (
            (None, 400),
            (FakeUpload(payload=b""), 400),
            (FakeUpload(filename="sample.exe", content_type="application/octet-stream"), 415),
            (FakeUpload(filename="sample.ogg", content_type="image/png"), 415),
        )
        for upload, expected_status in cases:
            with self.subTest(expected_status=expected_status, filename=getattr(upload, "filename", None)):
                with self.assertRaises(FakeHTTPException) as raised:
                    self.invoke(self.request(upload))
                self.assertEqual(raised.exception.status_code, expected_status)
        self.remote.assert_not_awaited()

    def test_oversized_upload_is_rejected(self):
        oversized = FakeUpload(payload=b"x" * (self.module.MAX_UPLOAD_BYTES + 1))
        with self.assertRaises(FakeHTTPException) as raised:
            self.invoke(self.request(oversized))
        self.assertEqual(raised.exception.status_code, 413)
        self.assertTrue(oversized.closed)
        self.remote.assert_not_awaited()

    def test_language_and_response_format_are_validated(self):
        for fields in ({"language": "en"}, {"response_format": "text"}):
            with self.subTest(fields=fields):
                upload = FakeUpload()
                with self.assertRaises(FakeHTTPException) as raised:
                    self.invoke(self.request(upload, fields=fields))
                self.assertEqual(raised.exception.status_code, 400)
                self.assertTrue(upload.closed)
        self.remote.assert_not_awaited()

    def test_inference_errors_do_not_leak_details(self):
        self.remote.side_effect = RuntimeError("private-token-value")
        with self.assertLogs("modal_asr.http", level=logging.WARNING) as captured:
            with self.assertRaises(FakeHTTPException) as raised:
                self.invoke(self.request(self.upload))
        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn("private-token-value", raised.exception.detail)
        self.assertNotIn("private-token-value", "\n".join(captured.output))
        self.assertTrue(self.upload.closed)


if __name__ == "__main__":
    unittest.main()