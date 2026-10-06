"""Offline adapter tests: python3 -m unittest discover -s tests -p test_asr_backends.py."""
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pipeline import asr


class TimeoutErrorStub(Exception):
    pass


class RequestErrorStub(Exception):
    pass


class ASRBackendTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "ASR_BACKEND": "hosted", "HOSTED_ASR_URL": "https://asr.example.invalid/transcribe",
            "HOSTED_ASR_API_KEY": "", "HOSTED_ASR_TIMEOUT_SECONDS": "60", "HOSTED_ASR_TEXT_FIELD": "text",
        })
        self.env.start()
        asr._provider = None
        self.addCleanup(self.env.stop)
        self.addCleanup(setattr, asr, "_provider", None)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.audio = str(Path(self.temp.name) / 'sample.wav')
        Path(self.audio).write_bytes(b'offline test fixture')

    def request(self, response=None, error=None):
        client = Mock()
        client.post.return_value = response
        client.post.side_effect = error
        context = Mock()
        context.__enter__ = Mock(return_value=client)
        context.__exit__ = Mock(return_value=False)
        module = SimpleNamespace(Client=Mock(return_value=context), TimeoutException=TimeoutErrorStub, RequestError=RequestErrorStub)
        with patch.dict(sys.modules, {'httpx': module}):
            result = asr.transcribe_audio(self.audio)
        return result, client

    def test_hosted_does_not_load_or_import_local_whisper(self):
        with patch.object(asr.LocalWhisperASR, '_load', side_effect=AssertionError('Whisper loaded')), patch.dict(sys.modules, {'torch': None, 'transformers': None}):
            self.assertIsInstance(asr.get_asr_provider(), asr.HostedASR)
            asr.preload_asr()
            result, _ = self.request(Mock(status_code=200, json=Mock(return_value={'text': 'test transcription'})))
            self.assertEqual(result, 'test transcription')

    def test_local_selection_is_lazy(self):
        os.environ['ASR_BACKEND'] = 'local'
        os.environ['HOSTED_ASR_URL'] = ''
        with patch.dict(sys.modules, {'torch': None, 'transformers': None}):
            provider = asr.get_asr_provider()
        self.assertIsInstance(provider, asr.LocalWhisperASR)
        self.assertIsNone(provider._model)

    def test_local_model_cached_and_configuration_preserved(self):
        os.environ['ASR_BACKEND'] = 'local'
        processor = Mock()
        model = Mock()
        model.to.return_value = model
        hf = SimpleNamespace(AutoProcessor=Mock(from_pretrained=Mock(return_value=processor)), AutoModelForSpeechSeq2Seq=Mock(from_pretrained=Mock(return_value=model)))
        torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        with patch.dict(sys.modules, {'torch': torch, 'transformers': hf}):
            provider = asr.get_asr_provider()
            provider._load()
            provider._load()
        hf.AutoProcessor.from_pretrained.assert_called_once_with(asr.ASR_MODEL_ID)
        hf.AutoModelForSpeechSeq2Seq.from_pretrained.assert_called_once_with(asr.ASR_MODEL_ID)
        self.assertEqual(model.generation_config.language, 'sinhala')
        self.assertEqual(model.generation_config.task, 'transcribe')
        model.to.assert_called_once_with('cpu')

    def test_concurrent_local_initialization_happens_once(self):
        from concurrent.futures import ThreadPoolExecutor
        os.environ['ASR_BACKEND'] = 'local'
        model = Mock()
        model.to.return_value = model
        hf = SimpleNamespace(AutoProcessor=Mock(from_pretrained=Mock(return_value=Mock())), AutoModelForSpeechSeq2Seq=Mock(from_pretrained=Mock(return_value=model)))
        torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        provider = asr.get_asr_provider()
        with patch.dict(sys.modules, {'torch': torch, 'transformers': hf}), ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda _: provider._load(), range(8)))
        hf.AutoModelForSpeechSeq2Seq.from_pretrained.assert_called_once()

    def test_invalid_backend(self):
        os.environ['ASR_BACKEND'] = 'invalid'
        with self.assertRaisesRegex(asr.ASRConfigurationError, 'local or hosted'):
            asr.get_asr_provider()

    def test_missing_hosted_url(self):
        os.environ['HOSTED_ASR_URL'] = ''
        with self.assertRaises(asr.ASRConfigurationError):
            asr.get_asr_provider()

    def test_invalid_timeout(self):
        for value in ['0', '-1', 'nan', 'inf', 'wrong']:
            os.environ['HOSTED_ASR_TIMEOUT_SECONDS'] = value
            with self.assertRaises(asr.ASRConfigurationError):
                asr.HostedASR()

    def test_text_response_and_no_auth(self):
        result, client = self.request(Mock(status_code=200, json=Mock(return_value={'text': 'test transcription'})))
        self.assertEqual(result, 'test transcription')
        self.assertEqual(client.post.call_args.kwargs['headers'], {})
        audio = client.post.call_args.kwargs['files']['file'][1]
        self.assertTrue(audio.closed)

    def test_configured_text_field_and_auth(self):
        os.environ['HOSTED_ASR_TEXT_FIELD'] = 'transcript'
        os.environ['HOSTED_ASR_API_KEY'] = 'dummy-offline-key'
        result, client = self.request(Mock(status_code=200, json=Mock(return_value={'transcript': 'result'})))
        self.assertEqual(result, 'result')
        self.assertEqual(client.post.call_args.kwargs['headers'], {'Authorization': 'Bearer dummy-offline-key'})

    def test_timeout(self):
        with self.assertRaises(asr.ASRError) as context:
            self.request(error=TimeoutErrorStub('sensitive provider diagnostic'))
        self.assertEqual(context.exception.status_code, 504)
        self.assertNotIn('sensitive', str(context.exception))

    def test_network_failure(self):
        with self.assertRaises(asr.ASRError) as context:
            self.request(error=RequestErrorStub('sensitive provider diagnostic'))
        self.assertEqual(context.exception.status_code, 503)

    def test_non_success(self):
        for status in [302, 401, 429, 500]:
            with self.assertRaises(asr.ASRError) as context:
                self.request(Mock(status_code=status))
            self.assertEqual(context.exception.status_code, 502)

    def test_invalid_json(self):
        with self.assertRaisesRegex(asr.ASRError, 'invalid JSON'):
            self.request(Mock(status_code=200, json=Mock(side_effect=ValueError('bad'))))

    def test_missing_or_invalid_text(self):
        for payload in [{}, {'text': None}, {'text': 4}, [], 'text']:
            with self.assertRaisesRegex(asr.ASRError, 'transcription string'):
                self.request(Mock(status_code=200, json=Mock(return_value=payload)))

    def test_empty_text_preserves_endpoint_handling(self):
        result, _ = self.request(Mock(status_code=200, json=Mock(return_value={'text': ''})))
        self.assertEqual(result, '')


if __name__ == '__main__':
    unittest.main()
