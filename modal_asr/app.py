import logging
import mimetypes
import os
import subprocess
import tempfile
import time
import hmac
from pathlib import Path

import modal

MODEL_ID = "Lingalingeswaran/whisper-small-sinhala"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MODEL_CACHE_DIR = "/model-cache"
HF_CACHE_DIR = f"{MODEL_CACHE_DIR}/huggingface"
HF_HUB_CACHE_DIR = f"{HF_CACHE_DIR}/hub"
TORCH_CACHE_DIR = f"{MODEL_CACHE_DIR}/torch"
AUTH_SECRET_NAME = "paddyguard-modal-asr-auth"
AUTH_ENV_NAME = "PADDYGUARD_ASR_API_KEY"
MAX_MULTIPART_OVERHEAD_BYTES = 64 * 1024
SUPPORTED_AUDIO_TYPES = {
    ".ogg": {"audio/ogg", "application/ogg", "audio/vorbis"},
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"},
    ".mp3": {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mpeg-3"},
    ".m4a": {"audio/mp4", "audio/x-m4a"},
    ".webm": {"audio/webm"},
}

app = modal.App("paddyguard-modal-asr")
volume = modal.Volume.from_name("paddyguard-whisper-small-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg", "libsndfile1")
    .pip_install(
        "torch==2.5.1",
        "transformers==4.46.3",
        "soundfile==0.12.1",
        "numpy==2.1.3",
    )
    .env(
        {
            "HF_HOME": HF_CACHE_DIR,
            "HF_HUB_CACHE": HF_HUB_CACHE_DIR,
            "TORCH_HOME": TORCH_CACHE_DIR,
        }
    )
)
http_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi==0.115.12", "python-multipart==0.0.20")
)


def _ensure_valid_upload(file_bytes: bytes, filename: str) -> None:
    if not file_bytes:
        raise ValueError("Empty upload")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Upload too large")
    if not filename:
        raise ValueError("Missing filename")


@app.function(
    image=image,
    volumes={MODEL_CACHE_DIR: volume},
    timeout=600,
    scaledown_window=180,
    max_containers=1,
)
def transcribe_uploaded(file_bytes: bytes, filename: str):
    _ensure_valid_upload(file_bytes, filename)
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    import soundfile as sf

    if not hasattr(transcribe_uploaded, "_loaded"):
        start_time = time.perf_counter()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger = logging.getLogger("modal_asr")
        logger.info("[modal-asr] loading model=%s device=%s", MODEL_ID, device)

        processor = AutoProcessor.from_pretrained(MODEL_ID, cache_dir=HF_HUB_CACHE_DIR)
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            MODEL_ID,
            cache_dir=HF_HUB_CACHE_DIR,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device)
        model.eval()
        model.generation_config.language = "sinhala"
        model.generation_config.task = "transcribe"
        model.generation_config.forced_decoder_ids = None

        transcribe_uploaded._loaded = True
        transcribe_uploaded._processor = processor
        transcribe_uploaded._model = model
        transcribe_uploaded._device = device
        transcribe_uploaded._load_seconds = time.perf_counter() - start_time
        logger.info("[modal-asr] model_loaded model=%s device=%s load_seconds=%.3f", MODEL_ID, device, transcribe_uploaded._load_seconds)

    processor = transcribe_uploaded._processor
    model = transcribe_uploaded._model
    device = transcribe_uploaded._device

    suffix = Path(filename).suffix.lower() or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as src_file:
        src_path = Path(src_file.name)
        src_file.write(file_bytes)

    wav_path = src_path.with_suffix(".wav")
    if src_path.suffix.lower() != ".wav":
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "wav",
            str(wav_path),
        ]
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        wav_path = src_path

    try:
        audio, sample_rate = sf.read(str(wav_path), dtype="float32", always_2d=False)
        if audio.size == 0:
            raise ValueError("Empty audio after decoding")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sample_rate != 16000:
            audio = audio.astype("float32")
        inputs = processor(audio, sampling_rate=16000, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        start = time.perf_counter()
        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=256)
        transcript = processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        inference_seconds = time.perf_counter() - start
        if not transcript:
            raise ValueError("Transcription empty")
        return {
            "text": transcript,
            "model": MODEL_ID,
            "language": "si",
            "inference_seconds": round(inference_seconds, 3),
        }
    finally:
        for candidate in (src_path, wav_path):
            try:
                if candidate.exists():
                    candidate.unlink()
            except OSError:
                pass


@app.function(
    image=http_image,
    secrets=[modal.Secret.from_name(AUTH_SECRET_NAME, required_keys=[AUTH_ENV_NAME])],
    scaledown_window=180,
    max_containers=1,
)
@modal.asgi_app()
def listen_app():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse

    web_app = FastAPI()

    @web_app.post("/listen")
    async def listen(request: Request):
        expected_token = os.getenv(AUTH_ENV_NAME, "").strip()
        if not expected_token:
            raise HTTPException(status_code=503, detail="ASR authentication is not configured")

        authorization = request.headers.get("authorization", "")
        scheme, separator, supplied_token = authorization.partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not hmac.compare_digest(supplied_token.strip(), expected_token)
        ):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
                headers={"WWW-Authenticate": "Bearer"},
            )

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid request size") from None
            if declared_size > MAX_UPLOAD_BYTES + MAX_MULTIPART_OVERHEAD_BYTES:
                raise HTTPException(status_code=413, detail="Audio upload too large")

        try:
            form_data = await request.form(max_files=1, max_fields=4, max_part_size=MAX_UPLOAD_BYTES)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid multipart form upload") from None

        uploaded = form_data.get("file")
        if uploaded is None or not hasattr(uploaded, "read"):
            raise HTTPException(status_code=400, detail="Missing file field")

        filename = Path(getattr(uploaded, "filename", "") or "").name
        extension = Path(filename).suffix.lower()
        if not filename:
            await uploaded.close()
            raise HTTPException(status_code=400, detail="Missing filename")
        if extension not in SUPPORTED_AUDIO_TYPES:
            await uploaded.close()
            raise HTTPException(status_code=415, detail="Unsupported audio format")

        content_type = (getattr(uploaded, "content_type", "") or "").split(";", 1)[0].strip().lower()
        if content_type and content_type != "application/octet-stream":
            accepted_types = SUPPORTED_AUDIO_TYPES[extension]
            guessed_type, _ = mimetypes.guess_type(filename)
            if content_type not in accepted_types and content_type != guessed_type:
                await uploaded.close()
                raise HTTPException(status_code=415, detail="Unsupported audio content type")

        language = str(form_data.get("language", "si")).strip().lower()
        response_format = str(form_data.get("response_format", "json")).strip().lower()
        if language not in {"", "si"}:
            await uploaded.close()
            raise HTTPException(status_code=400, detail="Only Sinhala transcription is supported")
        if response_format not in {"", "json"}:
            await uploaded.close()
            raise HTTPException(status_code=400, detail="Only JSON responses are supported")

        try:
            file_bytes = await uploaded.read(MAX_UPLOAD_BYTES + 1)
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Empty audio upload")
            if len(file_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Audio upload too large")

            try:
                result = await transcribe_uploaded.remote.aio(
                    file_bytes=file_bytes,
                    filename=filename,
                )
            except Exception as exc:
                logging.getLogger("modal_asr.http").warning(
                    "ASR inference unavailable (exception_type=%s)", type(exc).__name__
                )
                raise HTTPException(status_code=503, detail="ASR inference unavailable") from None

            transcript = result.get("text") if isinstance(result, dict) else None
            if not isinstance(transcript, str) or not transcript.strip():
                raise HTTPException(status_code=503, detail="ASR inference returned no transcript")

            response = {
                "text": transcript,
                "model": MODEL_ID,
                "language": "si",
            }
            inference_seconds = result.get("inference_seconds")
            if isinstance(inference_seconds, (int, float)) and not isinstance(inference_seconds, bool):
                response["inference_seconds"] = inference_seconds
            return JSONResponse(response)
        finally:
            await uploaded.close()

    return web_app


@app.local_entrypoint()
def run(audio_path: str):
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)
    with open(audio_path, "rb") as handle:
        payload = handle.read()
    result = transcribe_uploaded.remote(file_bytes=payload, filename=os.path.basename(audio_path) or "audio.wav")
    print(result)
