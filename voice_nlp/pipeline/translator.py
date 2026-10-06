"""
Translation Module: Sinhala text -> English text.

Uses translators library (NOT deep-translator GoogleTranslator which is broken).
3-layer fallback:
  Layer 1: translators → Google engine
  Layer 2: translators → Bing engine
  Layer 3: Sinhala keyword direct mapping

This matches exactly what worked in Colab notebook English_Output_Old.ipynb.
"""
import logging, time

logger = logging.getLogger("voice_nlp.translator")

# ── Correction table ───────────────────────────────────────────────────────────
CORRECTIONS = {
    "krispy kreme"     : "diamond shaped gray lesion leaf blast on paddy leaf",
    "krispy"           : "diamond shaped gray lesion leaf blast on paddy leaf",
    "milky rice"       : "diamond shaped gray lesion leaf blast on paddy leaf",
    "milk rice"        : "diamond shaped gray lesion leaf blast on paddy leaf",
    "rice cake"        : "diamond shaped gray lesion leaf blast on paddy leaf",
    "kiribath"         : "diamond shaped gray lesion leaf blast on paddy leaf",
    "patches of milky" : "diamond shaped gray spots leaf blast on paddy",
    "barley"           : "paddy rice leaf yellowing disease",
    "goliath"          : "paddy leaf yellow stripe bacterial blight",
    "perri"            : "paddy leaf yellowing disease symptom",
    "perry"            : "paddy leaf yellowing disease symptom",
    "good for you"     : "paddy leaf yellowing discoloration disease",
    "hooray"           : "paddy plant disease symptom",
    "has stitches"     : "diamond shaped spots on paddy leaf blast",
    "turned black"     : "paddy leaf yellowing discoloration",
    "jaws"             : "spots marks paddy leaf brown disease",
    "porridge"         : "paddy leaf yellowing disease symptom",
    "corn"             : "paddy leaf crop disease symptom",
}

# ── Sinhala keyword fallback ───────────────────────────────────────────────────
SINHALA_KEYWORDS = {
    "කහපාටයි"   : "yellow paddy leaf margin stripe bacterial blight",
    "කහ"        : "yellow paddy leaf margin stripe bacterial blight",
    "ආන්තරේ"    : "leaf margin yellow bacterial blight",
    "රේඛා"      : "stripe yellow leaf bacterial blight",
    "ශ්‍රාවය"   : "bacterial ooze milky droplets stem blight",
    "කිරිබත්"   : "diamond shaped gray lesion leaf blast on paddy leaf",
    "ඩයමන්ඩ්"   : "diamond spindle shaped spot gray leaf blast",
    "ඩයිමන්ඩ්"  : "diamond spindle shaped spot gray leaf blast",
    "පාළු"      : "leaf blast spot paddy disease",
    "අළු"       : "gray grey spot blast paddy leaf",
    "ලකුණු"     : "spot lesion paddy leaf disease",
    "පුල්ලි"    : "spots lesions paddy leaf disease",
    "දුඹුරුපාට" : "brown oval spot paddy leaf disease",
    "දුඹුරු"    : "brown oval spot paddy leaf disease",
    "ලප"        : "spots brown round paddy leaf disease",
    "ගොඩාක්"    : "many spots paddy leaf disease",
    "හොඳ"       : "healthy paddy no disease",
    "ගෙදර"      : "going home non disease unrelated",
    "යනවා"      : "going non disease unrelated",
    "මම"        : "personal statement non disease",
}


def apply_correction(text: str) -> str:
    """Replace known garbled translations with correct disease keywords."""
    t = text.lower()
    for trigger, fix in CORRECTIONS.items():
        if trigger in t:
            logger.info("Correction applied: '%s'", trigger)
            return fix
    return text


def _keyword_fallback(sinhala_text: str) -> str:
    """Scan Sinhala text directly for disease keywords when all translators fail."""
    for kw, english in SINHALA_KEYWORDS.items():
        if kw in sinhala_text:
            logger.info("Keyword match: '%s'", kw)
            return english
    return "paddy plant disease symptom leaf spot"


def translate_to_english(sinhala_text: str) -> str:
    """
    Translate Sinhala text to English.
    Try each translator ONCE — no retry loops.
    Matches Colab notebook Cell 3 exactly.
    """
    import translators as ts

    # ── Layer 1: Google via translators library ────────────────────────────
    try:
        raw = ts.translate_text(
            sinhala_text,
            from_language = "si",
            to_language   = "en"
        )
        if raw and len(raw.strip()) > 0:
            corrected = apply_correction(raw)
            logger.info("Translation: '%s' → raw='%s' → corrected='%s'",
                        sinhala_text, raw, corrected)
            return corrected
    except Exception as e:
        logger.warning("Google (translators) failed: %s", e)

    # ── Layer 2: Bing via translators library ─────────────────────────────
    try:
        raw = ts.translate_text(
            sinhala_text,
            translator    = "bing",
            from_language = "si",
            to_language   = "en"
        )
        if raw and len(raw.strip()) > 0:
            corrected = apply_correction(raw)
            logger.info("Bing translation: '%s' → '%s'", raw, corrected)
            return corrected
    except Exception as e:
        logger.warning("Bing (translators) failed: %s", e)

    # ── Layer 3: Sinhala keyword fallback ─────────────────────────────────
    logger.warning("All translators failed — keyword fallback for: %s", sinhala_text)
    return _keyword_fallback(sinhala_text)
