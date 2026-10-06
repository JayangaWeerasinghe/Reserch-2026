"""
Adaptive follow-up question logic for low-confidence diagnoses.
All questions are bilingual — Sinhala first, English below for reference.
Answers accepted in Sinhala (ඔව්/නෑ) or English (yes/no).
"""

# ── Sinhala yes/no answer map ──────────────────────────────────────────
# When farmer answers, convert Sinhala to English before re-classifying
SINHALA_YES = {
    "ඔව්", "ඔවු", "ඔව", "ඔයි", "හා", "හාං",
    "yes", "y", "yeah", "yep", "correct", "true",
    "맞아", "あ", "ok", "okay", "sure", "right"
}
SINHALA_NO = {
    "නෑ", "නැ", "නැහැ", "නො", "නොවේ", "නේ",
    "no", "n", "nope", "not", "false", "wrong", "nah"
}

# ── Bilingual question bank ────────────────────────────────────────────
# Each question: (Sinhala question, English symptom keywords for SVM)
FOLLOWUP_QUESTIONS = {

    "Bacterial Blight": [
        {
            "sinhala" : "කොළ ආන්තරේ කහ පාට වී රැලි සහිත කහ රේඛා පෙනෙනවා ද?",
            "english" : "Are the leaf margins turning yellow or developing wavy yellow stripes?",
            "yes_hint": "yellow wavy stripe leaf margin bacterial blight",
            "no_hint" : "no yellow stripe leaf margin",
        },
        {
            "sinhala" : "උදෑසන කොළ ලේශනය මත කිරි බිංදු දකිනවා ද?",
            "english" : "Can you see milky drops on the lesion early in the morning?",
            "yes_hint": "milky ooze droplets lesion bacterial blight",
            "no_hint" : "no milky drops lesion",
        },
        {
            "sinhala" : "වී පැල හදිසියේම මැලවී ගොස් අළු-කොළ පැහැති රෝල් කරන ලද කොළ තිබේද?",
            "english" : "Have the seedlings wilted suddenly with grayish-green rolled leaves?",
            "yes_hint": "kresek seedling wilting gray green rolled bacterial blight",
            "no_hint" : "no wilting rolled leaves",
        },
    ],

    "Leaf Blast": [
        {
            "sinhala" : "ලප දියමන්ති හෝ දිගු කිරිබත් හැඩැති ද?",
            "english" : "Are the spots diamond-shaped or long, milkrice-shaped?",
            "yes_hint": "diamond spindle shaped spot pointed leaf blast",
            "no_hint" : "no diamond shape spots",
        },
        {
            "sinhala" : "ලප මැද අළු හෝ සුදු පාට වන අතර දාර දුඹුරු හෝ රතු ද?",
            "english" : "Are the spots gray or white in the center with a brown or red border?",
            "yes_hint": "gray white center brown red border lesion blast",
            "no_hint" : "no gray center spots",
        },
        {
            "sinhala" : "සිසිල් හෝ වැසි කාලයකින් පසු ලප ඇති වූනා ද?",
            "english" : "Have the spots appeared after a cool or rainy period?",
            "yes_hint": "cool rainy weather spots appearing leaf blast",
            "no_hint" : "no cool rainy period",
        },
    ],

    "Brown Spot": [
        {
            "sinhala" : "ලප රවුම් හෝ ඕවල් හැඩයෙන් දුඹුරු පාට වන අතර කහ වලල්ලක් වටෙට තිබෙද?",
            "english" : "Are the spots round or oval with a brownish color and a yellow ring?",
            "yes_hint": "round oval brown spot yellow halo ring fungal",
            "no_hint" : "no round oval spots",
        },
        {
            "sinhala" : "ඔබේ ගොයම් කුඹුර පෝෂ්‍ය පදාර්ථ අඩු හෝ ජලය නැති ද?",
            "english" : "Is the soil in your field nutrient-deficient or unflooded?",
            "yes_hint": "nutrient deficient unflooded soil brown spot",
            "no_hint" : "no nutrient deficiency flooded field",
        },
        {
            "sinhala" : "ධාන්‍ය වර්ණ වෙනස් වී ඇති හෝ ලප දකිනවා ද?",
            "english" : "Are the grains discolored or showing spotting?",
            "yes_hint": "grain discoloration spotting brown spot pecky rice",
            "no_hint" : "no grain discoloration",
        },
    ],
}

# ── Default fallback ───────────────────────────────────────────────────
_DEFAULT = [
    {
        "sinhala" : "ගොයම් කොළ, කඳ, හෝ ධාන්‍යය ගැන වැඩිදුර ලක්ෂණ කියා දෙන්න.",
        "english" : "Can you describe more symptoms of your paddy plant?",
        "yes_hint": "disease symptom paddy leaf",
        "no_hint" : "no symptoms",
    }
]


def get_followup_question(disease_prediction: str, question_index: int = 0) -> dict:
    """
    Returns the bilingual question dict for the given disease and index.
    Returns: { "sinhala": "...", "english": "...", "yes_hint": "...", "no_hint": "..." }
    """
    questions = FOLLOWUP_QUESTIONS.get(disease_prediction, _DEFAULT)
    return questions[min(question_index, len(questions) - 1)]


def resolve_answer(answer: str, question: dict) -> str:
    """
    Convert farmer's Sinhala/English yes-no answer into English symptom text
    that the SVM classifier can re-classify confidently.

    If farmer says ඔව්  → return yes_hint (strong symptom keywords)
    If farmer says නෑ   → return no_hint
    Otherwise           → return the answer as-is (let SVM try)
    """
    cleaned = answer.strip().lower()

    # Remove punctuation for matching
    cleaned_words = set(cleaned.replace(".", "").replace(",", "").split())

    if cleaned_words & SINHALA_YES:
        return question["yes_hint"]

    if cleaned_words & SINHALA_NO:
        return question["no_hint"]

    # Free-text answer — return as-is, SVM will classify
    return answer