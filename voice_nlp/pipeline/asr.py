"""
ASR Module: Converts Sinhala audio to Sinhala text.
Uses: Lingalingeswaran/whisper-small-sinhala

"""
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import torch, librosa, os, logging

logger = logging.getLogger("voice_nlp.asr")

ASR_MODEL_ID = os.getenv("ASR_MODEL_ID", "Lingalingeswaran/whisper-small-sinhala")

_asr_processor = None
_asr_model     = None
_device        = "cuda" if torch.cuda.is_available() else "cpu"

logger.info("PyTorch: %s  |  CUDA: %s",
            torch.__version__,
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else "Not available")


def _load_asr():
    global _asr_processor, _asr_model
    if _asr_processor is None:
        logger.info("Loading ASR model: %s on %s", ASR_MODEL_ID, _device)
        _asr_processor = AutoProcessor.from_pretrained(ASR_MODEL_ID)
        _asr_model     = AutoModelForSpeechSeq2Seq.from_pretrained(ASR_MODEL_ID)
        _asr_model     = _asr_model.to(_device)
        # Set language via generation_config — same as Colab notebook
        _asr_model.generation_config.language = "sinhala"
        _asr_model.generation_config.task     = "transcribe"
        logger.info("ASR model loaded on %s", _device)


def preload_asr() -> None:
    """Load the ASR model eagerly (called at service startup).

    Without this, the model loads lazily on the first /diagnose call,
    which can take several minutes and blow past the gateway's timeout.
    """
    _load_asr()


def transcribe_audio(audio_path: str) -> str:
    """
    Convert audio file to Sinhala text transcript.
    Exact same approach as Colab notebook Cell 4.
    """
    _load_asr()
    audio_array, _ = librosa.load(audio_path, sr=16000)
    input_features = _asr_processor(
        audio_array,
        sampling_rate  = 16000,
        return_tensors = "pt"
    ).input_features.to(_device)

    with torch.no_grad():
        # NO extra parameters — clean generate() call matching Colab exactly
        predicted_ids = _asr_model.generate(input_features)

    transcript = _asr_processor.batch_decode(
        predicted_ids,
        skip_special_tokens = True
    )[0]

    logger.info("Transcript: %s", transcript)
    return transcript
