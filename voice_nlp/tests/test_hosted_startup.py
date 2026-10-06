"""Full-runtime offline tests; requires installed service dependencies."""
import subprocess
import sys
from pathlib import Path


def test_hosted_application_startup_and_health_without_whisper():
    # Fresh interpreter blocks all local ASR imports, not just from_pretrained.
    code = '''
import os, sys
os.environ.update(ASR_BACKEND="hosted", HOSTED_ASR_URL="https://asr.example.invalid/transcribe")
sys.modules["torch"] = None
sys.modules["transformers"] = None
from fastapi.testclient import TestClient
from pipeline import asr
from unittest.mock import patch
with patch.object(asr.LocalWhisperASR, "_load", side_effect=AssertionError("Whisper initialized")), patch.object(asr.HostedASR, "transcribe", side_effect=AssertionError("Health called ASR")):
    from main import app
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").json()["service"] == "voice_nlp"
'''
    subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1], check=True)


def test_artifacts_load_with_training_sklearn_version():
    import sklearn
    import warnings
    from sklearn.exceptions import InconsistentVersionWarning
    from pipeline import classifier
    assert sklearn.__version__ == '1.6.1'
    with warnings.catch_warnings():
        warnings.simplefilter('error', InconsistentVersionWarning)
        classifier.load_models()
    assert classifier._classifier is not None
    assert classifier._tfidf is not None
    assert classifier.classify_with_ood('yellow')['is_ood'] is True


def test_diagnose_contract_and_temporary_audio_cleanup(monkeypatch):
    from fastapi.testclient import TestClient
    from api import endpoints
    from main import app
    from pathlib import Path
    from types import SimpleNamespace
    paths = []
    def transcribe(path):
        assert Path(path).exists()
        paths.append(path)
        return 'test Sinhala transcript'
    monkeypatch.setattr(endpoints, 'check_audio_quality', lambda path: SimpleNamespace(passed=True, snr=20, silence_ratio=0, duration=2, to_dict=lambda: {'passed': True}))
    monkeypatch.setattr(endpoints, 'transcribe_audio', transcribe)
    monkeypatch.setattr(endpoints, 'translate_to_english', lambda text: 'brown spots on paddy leaf')
    monkeypatch.setattr(endpoints, 'score_severity', lambda *args: {'level': 'mild'})
    monkeypatch.setattr(endpoints, 'classify_with_ood', lambda text: {'disease': 'Brown Spot', 'label_id': 2, 'confidence': 0.95, 'is_ood': False, 'needs_followup': False, 'all_scores': {}, 'status': 'Confident', 'message': None, 'ood_reason': None})
    monkeypatch.setattr(endpoints, 'synthesise_result', lambda **kwargs: 'dummy-audio')
    response = TestClient(app).post('/diagnose', files={'audio': ('test.wav', b'fixture', 'audio/wav')})
    assert response.status_code == 200
    result = response.json()
    assert result['disease'] == 'Brown Spot'
    assert result['sinhala_transcript'] == 'test Sinhala transcript'
    assert result['english_translation'] == 'brown spots on paddy leaf'
    assert result['tts_audio_b64'] == 'dummy-audio'
    assert result['confidence_trajectory'] == []
    assert not Path(paths[0]).exists()
