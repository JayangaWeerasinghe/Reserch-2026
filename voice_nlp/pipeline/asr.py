"""ASR deployment adapter; local Whisper remains the research backend.

Both providers preserve transcribe_audio(path) -> transcript text. Hosted mode
never imports local Whisper dependencies or downloads its weights.
"""
import logging
import math
import mimetypes
import os
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

logger = logging.getLogger("voice_nlp.asr")
ASR_MODEL_ID = os.getenv("ASR_MODEL_ID", "Lingalingeswaran/whisper-small-sinhala")


class ASRConfigurationError(ValueError):
    """Invalid mode-specific environment configuration (safe to display)."""


class ASRError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class LocalWhisperASR:
    def __init__(self):
        self._processor = None
        self._model = None
        self._device = None
        self._lock = Lock()

    def _load(self):
        with self._lock:
            if self._model is not None:
                return
            # Import and instantiate only when local inference is requested.
            import torch
            from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("[asr] loading local Whisper model on %s", device)
            processor = AutoProcessor.from_pretrained(ASR_MODEL_ID)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(ASR_MODEL_ID).to(device)
            model.generation_config.language = "sinhala"
            model.generation_config.task = "transcribe"
            # Publish the cached pair only after successful initialization.
            self._processor, self._model, self._device = processor, model, device
            logger.info("[asr] local Whisper model ready")

    def transcribe(self, audio_path: str) -> str:
        self._load()
        import torch
        import librosa
        audio_array, _ = librosa.load(audio_path, sr=16000)
        input_features = self._processor(
            audio_array, sampling_rate=16000, return_tensors="pt"
        ).input_features.to(self._device)
        with torch.no_grad():
            predicted_ids = self._model.generate(input_features)
        return self._processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]


class HostedASR:
    """POST multipart `file`; expect a top-level configurable string field."""
    def __init__(self):
        self.url = os.getenv("HOSTED_ASR_URL", "").strip()
        try:
            parsed = urlsplit(self.url)
            valid_url = parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username and not parsed.password and not parsed.fragment
            parsed.port  # Validate port syntax without exposing the URL.
        except ValueError:
            valid_url = False
        if not valid_url:
            raise ASRConfigurationError("HOSTED_ASR_URL must be a valid HTTP(S) endpoint without embedded credentials")
        self.api_key = os.getenv("HOSTED_ASR_API_KEY", "").strip()
        self.text_field = os.getenv("HOSTED_ASR_TEXT_FIELD", "text").strip()
        if not self.text_field:
            raise ASRConfigurationError("HOSTED_ASR_TEXT_FIELD must not be empty")
        try:
            self.timeout = float(os.getenv("HOSTED_ASR_TIMEOUT_SECONDS", "60"))
            if not math.isfinite(self.timeout) or self.timeout <= 0:
                raise ValueError
        except ValueError:
            raise ASRConfigurationError("HOSTED_ASR_TIMEOUT_SECONDS must be a positive finite number") from None

    def transcribe(self, audio_path: str) -> str:
        import httpx
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with open(audio_path, "rb") as audio, httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.url, headers=headers,
                    files={"file": (Path(audio_path).name, audio, mimetypes.guess_type(audio_path)[0] or "application/octet-stream")},
                )
        except httpx.TimeoutException:
            raise ASRError("Hosted ASR request timed out", 504) from None
        except httpx.RequestError:
            raise ASRError("Hosted ASR service unavailable", 503) from None
        if not 200 <= response.status_code < 300:
            raise ASRError("Hosted ASR returned an unsuccessful HTTP status")
        try:
            payload = response.json()
        except ValueError:
            raise ASRError("Hosted ASR returned invalid JSON") from None
        if not isinstance(payload, dict) or not isinstance(payload.get(self.text_field), str):
            raise ASRError("Hosted ASR response is missing the configured transcription string")
        # Empty transcript follows the existing endpoint's HTTP 400 handling.
        return payload[self.text_field]


_provider = None
_provider_lock = Lock()


def get_asr_provider():
    global _provider
    with _provider_lock:
        if _provider is None:
            backend = os.getenv("ASR_BACKEND", "local").strip().lower()
            if backend == "local":
                _provider = LocalWhisperASR()
            elif backend == "hosted":
                _provider = HostedASR()
            else:
                raise ASRConfigurationError("ASR_BACKEND must be local or hosted")
            logger.info("[asr] backend=%s", backend)
        return _provider


def preload_asr() -> None:
    """Optional local research warmup; never used during API startup."""
    provider = get_asr_provider()
    if isinstance(provider, LocalWhisperASR):
        provider._load()


def transcribe_audio(audio_path: str) -> str:
    return get_asr_provider().transcribe(audio_path)
