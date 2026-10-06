"""
NLP Classifier with 5-Signal OOD Detection (v4).
Loads SVM + TF-IDF models and classifies English text.

"""
import joblib, os, numpy as np
from scipy.stats import entropy as scipy_entropy
from pipeline.preprocessor import preprocess_text
from pipeline.ood_detector import (
    OOD_THRESHOLD, FOLLOWUP_THRESHOLD, ENTROPY_THRESHOLD,
    MARGIN_THRESHOLD, MIN_TEXT_WORDS, MIN_SYMPTOM_WORDS,
    check_strong_bigram, count_symptom_words, count_blocklist_words,
)

LABEL_MAP = {0: "Bacterial Blight", 1: "Leaf Blast",
             2: "Brown Spot",       3: "Healthy"}

_classifier = None
_tfidf      = None

def load_models():
    global _classifier, _tfidf
    model_path = os.getenv("MODEL_PATH", "models/paddyguard_best_classifier.pkl")
    tfidf_path = os.getenv("TFIDF_PATH", "models/paddyguard_tfidf.pkl")
    if os.path.exists(model_path) and os.path.exists(tfidf_path):
        _classifier = joblib.load(model_path)
        _tfidf      = joblib.load(tfidf_path)
        print(f"[classifier] Models loaded from {model_path}")
    else:
        print(f"[classifier] WARNING: Model files not found. Place .pkl files in /models/")

def classify_with_ood(english_text: str) -> dict:
    """
    5-Signal OOD Detection:
    1. Text length gate
    2. Blocklist check
    3. Vocabulary check
    4. Confidence + Entropy
    5. Margin check
    """
    if _classifier is None:
        return {"error": "Models not loaded. Upload .pkl files to /models/"}

    words       = english_text.strip().split()
    n_words     = len(words)
    sym_count   = count_symptom_words(english_text)
    block_count = count_blocklist_words(english_text)
    has_bigram  = check_strong_bigram(english_text)

    def ood(reason, confidence=0.0, all_scores=None):
        return {
            "disease"       : "Unknown / OOD",
            "label_id"      : -1,
            "confidence"    : round(confidence, 4),
            "is_ood"        : True,
            "ood_reason"    : reason,
            "needs_followup": False,
            "status"        : f"OOD: {reason}",
            "message"       : "Please describe your paddy plant symptoms more clearly.",
            "all_scores"    : all_scores or {LABEL_MAP[i]: 0.0 for i in range(4)},
        }

    # Signal 1: Length gate
    if n_words < MIN_TEXT_WORDS:
        return ood(f"Too short ({n_words} words)")

    # Signal 2: Blocklist
    if block_count > 0 and not has_bigram and sym_count < 2:
        return ood("Non-disease topic detected")

    # Signal 3: Vocabulary
    if not has_bigram and sym_count < MIN_SYMPTOM_WORDS:
        return ood(f"Insufficient disease vocabulary ({sym_count} words)")

    # SVM inference
    clean    = preprocess_text(english_text)
    vec      = _tfidf.transform([clean])
    proba    = _classifier.predict_proba(vec)[0]
    conf     = float(proba.max())
    label_id = int(proba.argmax())
    ent      = float(scipy_entropy(proba, base=2))
    sorted_p = sorted(proba, reverse=True)
    margin   = sorted_p[0] - sorted_p[1]
    scores   = {LABEL_MAP[i]: round(float(p), 4) for i, p in enumerate(proba)}

    # Signal 4: Confidence + Entropy
    if conf < OOD_THRESHOLD:
        return ood(f"Low confidence ({conf:.3f})", conf, scores)
    if ent > ENTROPY_THRESHOLD:
        return ood(f"High entropy ({ent:.3f})", conf, scores)

    # Signal 5: Margin
    if margin < MARGIN_THRESHOLD:
        return ood(f"Ambiguous (margin={margin:.3f})", conf, scores)

    # Follow-up zone
    if conf < FOLLOWUP_THRESHOLD:
        return {
            "disease"       : LABEL_MAP[label_id],
            "label_id"      : label_id,
            "confidence"    : round(conf, 4),
            "is_ood"        : False,
            "ood_reason"    : None,
            "needs_followup": True,
            "status"        : "Low confidence — ask follow-up",
            "message"       : "Could you describe more symptoms to confirm the diagnosis?",
            "all_scores"    : scores,
        }

    # Confident
    return {
        "disease"       : LABEL_MAP[label_id],
        "label_id"      : label_id,
        "confidence"    : round(conf, 4),
        "is_ood"        : False,
        "ood_reason"    : None,
        "needs_followup": False,
        "status"        : f"Confident: {LABEL_MAP[label_id]}",
        "message"       : None,
        "all_scores"    : scores,
    }
