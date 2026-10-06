"""
Audio Quality Gate — Novelty 2
Validates audio signal quality BEFORE sending to Whisper ASR.
Prevents hallucination caused by silent, clipped, or noisy recordings.

Research contribution: First agricultural voice system to gate input
quality before ASR inference, reducing hallucination at source.
"""
import numpy as np
import librosa
import logging

logger = logging.getLogger("voice_nlp.audio_quality")


class AudioQualityResult:
    def __init__(
        self,
        passed: bool,
        reason: str | None = None,
        reason_en: str | None = None,
        snr: float | None = None,
        silence_ratio: float | None = None,
        duration: float | None = None,
        peak: float | None = None,
    ):
        self.passed        = passed
        self.reason        = reason         # Sinhala message for farmer
        self.reason_en     = reason_en      # English for logging
        self.snr           = snr
        self.silence_ratio = silence_ratio
        self.duration      = duration
        self.peak          = peak

    def to_dict(self) -> dict:
        return {
            "passed"       : self.passed,
            "reason"       : self.reason,
            "reason_en"    : self.reason_en,
            "snr_db"       : round(self.snr, 2) if self.snr is not None else None,
            "silence_ratio": round(self.silence_ratio, 3) if self.silence_ratio is not None else None,
            "duration_sec" : round(self.duration, 2) if self.duration is not None else None,
        }


def check_audio_quality(audio_path: str) -> AudioQualityResult:
    """
    Validate audio quality before ASR.
    Returns AudioQualityResult with passed=True if audio is usable.

    Checks performed:
      1. Duration gate     (1.5s – 30s)
      2. Silence ratio     (< 80% silence)
      3. Clipping check    (peak < 0.99)
      4. SNR estimate      (signal-to-noise ratio > 5dB)
    """
    try:
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
    except Exception as e:
        logger.error("Audio load failed: %s", e)
        return AudioQualityResult(
            passed    = False,
            reason    = "ශ්‍රව්‍ය ගොනුව කියවීමට නොහැකිය. නැවත උත්සාහ කරන්න.",
            reason_en = f"Audio file could not be read: {e}",
        )

    duration = len(audio) / sr

    # ── Check 1: Duration ─────────────────────────────────────────────
    if duration < 1.5:
        return AudioQualityResult(
            passed    = False,
            reason    = "ශ්‍රව්‍ය ගොනුව ඉතා කෙටිය. දිගු කාලයක් කතා කරන්න.",
            reason_en = f"Recording too short ({duration:.1f}s). Speak for at least 2 seconds.",
            duration  = duration,
        )
    if duration > 30:
        return AudioQualityResult(
            passed    = False,
            reason    = "ශ්‍රව්‍ය ගොනුව ඉතා දිගය. තත්පර 30ට අඩු කරන්න.",
            reason_en = f"Recording too long ({duration:.1f}s). Keep under 30 seconds.",
            duration  = duration,
        )

    # ── Check 2: Silence ratio ────────────────────────────────────────
    rms_frames    = librosa.feature.rms(y=audio, frame_length=1024, hop_length=512)[0]
    silence_ratio = float(np.mean(rms_frames < 0.01))
    if silence_ratio > 0.80:
        return AudioQualityResult(
            passed        = False,
            reason        = "කරුණාකර මයිකෆෝනයට ළඟ කතා කරන්න. ශ්‍රව්‍ය ශබ්දය ඉතා මෘදුය.",
            reason_en     = f"Too much silence ({silence_ratio*100:.0f}%). Speak clearly into the microphone.",
            duration      = duration,
            silence_ratio = silence_ratio,
        )

    # ── Check 3: Clipping ─────────────────────────────────────────────
    peak = float(np.max(np.abs(audio)))
    if peak > 0.99:
        return AudioQualityResult(
            passed    = False,
            reason    = "මයිකෆෝනය ඉතා ළඟ. ටිකක් දුරින් සිට කතා කරන්න.",
            reason_en = "Audio clipping detected. Move mic slightly further away.",
            duration  = duration,
            peak      = peak,
        )

    # ── Check 4: SNR estimate ─────────────────────────────────────────
    noise_floor  = float(np.percentile(np.abs(audio), 10))
    signal_peak  = float(np.percentile(np.abs(audio), 90))
    snr          = 20 * np.log10(signal_peak / (noise_floor + 1e-10))
    if snr < 5.0:
        return AudioQualityResult(
            passed    = False,
            reason    = "පසුබිම් ශබ්දය ඉතා වැඩිය. නිශ්ශබ්ද ස්ථානයකින් ශ්‍රව්‍ය ලබා ගන්න.",
            reason_en = f"Low SNR ({snr:.1f}dB). Reduce background noise.",
            duration  = duration,
            snr       = snr,
        )

    logger.info(
        "Audio quality OK: duration=%.1fs silence=%.2f snr=%.1fdB peak=%.3f",
        duration, silence_ratio, snr, peak
    )
    return AudioQualityResult(
        passed        = True,
        duration      = duration,
        snr           = snr,
        silence_ratio = silence_ratio,
        peak          = peak,
    )
