"""
Symptom Severity Scorer — Novelty 5
Estimates infection severity from the language intensity the farmer uses.

Research contribution: Adds a clinically useful second dimension beyond
disease class. No agricultural NLP system estimates severity from
symptom description language intensity.

Severity levels:
  severe   (3) — farmer uses high-intensity words: many, whole, everywhere
  moderate (2) — neutral intensity language
  mild     (1) — farmer uses low-intensity words: small, few, little, tip
"""
import logging

logger = logging.getLogger("voice_nlp.severity_scorer")

# ── High intensity words — suggest severe infection ───────────────────────────
SEVERITY_HIGH_SI = {
    # Sinhala high-intensity
    "ගොඩාක්", "ඉතාමත්", "මුලු", "සම්පූර්ණ", "ඉතා", "බොහෝ",
    "හැමතැන", "සෑම", "බොහොමයක්", "ඉතාම", "දැඩි",
}

SEVERITY_HIGH_EN = {
    # English high-intensity (from translation)
    "many", "very", "whole", "entire", "all", "severe", "severely",
    "heavily", "completely", "everywhere", "covered", "spreading",
    "lots", "numerous", "most", "full", "throughout", "extensive",
}

# ── Low intensity words — suggest mild infection ──────────────────────────────
SEVERITY_LOW_SI = {
    # Sinhala low-intensity
    "පොඩි", "ටිකක්", "ටිකේ", "ඇතැම්", "සමහර", "කෙළවරේ",
    "ආරම්භ", "ශීඝ්‍ර", "මදක්",
}

SEVERITY_LOW_EN = {
    # English low-intensity (from translation)
    "small", "little", "few", "some", "slight", "minor",
    "tip", "edge", "starting", "beginning", "early",
    "only", "just", "single",
}


def score_severity(sinhala_text: str, english_text: str) -> dict:
    """
    Estimate infection severity from symptom description language.

    Args:
        sinhala_text: Original Sinhala transcript from ASR
        english_text: English translation used for SVM classification

    Returns:
        {
            "level"    : "mild" | "moderate" | "severe",
            "score"    : 1 | 2 | 3,
            "label_si" : "මෘදු" | "මධ්‍යම" | "දරුණු",
            "label_en" : "Mild" | "Moderate" | "Severe",
        }
    """
    combined_si = sinhala_text
    combined_en = english_text.lower()

    # Count intensity signals
    high_si = sum(1 for w in SEVERITY_HIGH_SI if w in combined_si)
    high_en = sum(1 for w in SEVERITY_HIGH_EN if w in combined_en)
    low_si  = sum(1 for w in SEVERITY_LOW_SI  if w in combined_si)
    low_en  = sum(1 for w in SEVERITY_LOW_EN  if w in combined_en)

    total_high = high_si + high_en
    total_low  = low_si  + low_en

    if total_high >= 2:
        level = "severe"
    elif total_high >= 1 and total_low == 0:
        level = "severe"
    elif total_high >= 1 or total_low == 0:
        level = "moderate"
    else:
        level = "mild"

    LABELS = {
        "severe"  : {"score": 3, "label_si": "දරුණු",  "label_en": "Severe"},
        "moderate": {"score": 2, "label_si": "මධ්‍යම", "label_en": "Moderate"},
        "mild"    : {"score": 1, "label_si": "මෘදු",   "label_en": "Mild"},
    }

    result = {"level": level, **LABELS[level]}

    logger.info(
        "Severity: %s (high=%d low=%d)",
        level, total_high, total_low
    )
    return result
