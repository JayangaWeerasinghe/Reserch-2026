"""
Text-to-Speech Module — Novelty 4
Converts diagnosis result to natural Sinhala speech using gTTS.
Returns base64-encoded MP3 for direct playback in frontend <audio> element.

Research contribution: Completes the bidirectional voice accessibility loop.
Farmers with low literacy receive results as spoken Sinhala — not just text.
This addresses the TTS gap identified in all reviewed systems.
"""
import io, os, base64, logging
from gtts import gTTS

logger = logging.getLogger("voice_nlp.tts")

# ── Disease names in natural Sinhala speech ───────────────────────────────────
DISEASE_SINHALA_SPEECH = {
    "Bacterial Blight" : "බැක්ටීරියා අංගමාරය",
    "Leaf Blast"        : "කොල පාළු රෝගය",
    "Brown Spot"        : "දුඹුරු පුල්ලි රෝගය",
    "Healthy"           : "ඔබේ ගොයම් ගස සෞඛ්‍යමත්ය",
    "Unknown / OOD"     : "රෝගය හඳුනා ගත නොහැකිය",
}

# ── Severity labels in Sinhala ───────────────────────────────────────────────
SEVERITY_SINHALA = {
    "severe"  : "දරුණු",
    "moderate": "මධ්‍යම",
    "mild"    : "මෘදු",
}


def synthesise_result(
    disease       : str,
    confidence    : float,
    needs_followup: bool,
    is_ood        : bool = False,
    severity      : dict | None = None,
) -> str:
    """
    Convert diagnosis result to Sinhala speech.
    Returns base64-encoded MP3 string.
    Empty string returned on failure — never raises.

    Novelty 4: First working TTS in this pipeline.
    Enables low-literacy farmers to receive results by ear.
    """
    try:
        text = _build_speech_text(disease, confidence, needs_followup, is_ood, severity)
        logger.info("TTS synthesising: %s", text[:80])

        tts = gTTS(text=text, lang="si", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        audio_b64 = base64.b64encode(buf.read()).decode("utf-8")
        logger.info("TTS generated %d chars → %d bytes audio", len(text), len(audio_b64))
        return audio_b64

    except Exception as e:
        logger.error("TTS failed (non-fatal): %s", e)
        return ""


def synthesise_question(sinhala_question: str) -> str:
    """
    Convert a follow-up question to Sinhala speech.
    Returns base64-encoded MP3. Empty string on failure.
    """
    try:
        tts = gTTS(text=sinhala_question, lang="si", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception as e:
        logger.error("TTS question failed (non-fatal): %s", e)
        return ""


def _build_speech_text(
    disease       : str,
    confidence    : float,
    needs_followup: bool,
    is_ood        : bool,
    severity      : dict | None,
) -> str:
    """Build natural Sinhala speech text for the diagnosis result."""

    if is_ood:
        return (
            "ඔබේ ගොයම් රෝගය හඳුනා ගත නොහැකිය. "
            "කරුණාකර ගොයම් ලක්ෂණ ගැන වැඩිදුර විස්තර කරන්න."
        )

    disease_si = DISEASE_SINHALA_SPEECH.get(disease, disease)

    if disease == "Healthy":
        return (
            f"ඔබේ ගොයම් ගස සෞඛ්‍යමත් ය. "
            f"ගොයම් ගස නිතර නිරීක්ෂණය කරන්න."
        )

    if needs_followup:
        return (
            f"ආරම්භක රෝග නිර්ණය {disease_si}. "
            f"නිශ්චිත රෝගය තීරණය කිරීමට තවත් ප්‍රශ්නයකට පිළිතුරු දෙන්න."
        )

    severity_text = ""
    if severity and severity.get("level") != "mild":
        sev_si = SEVERITY_SINHALA.get(severity.get("level", ""), "")
        if sev_si:
            severity_text = f" රෝගය {sev_si} මට්ටමේ ඇත."

    return (
        f"ඔබේ ගොයම් ගසට {disease_si} ඇත.{severity_text} "
        f"ප්‍රතිකාර සඳහා නිර්දේශ කොටස බලන්න."
    )
