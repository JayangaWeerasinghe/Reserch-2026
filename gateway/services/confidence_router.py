"""
Confidence routing logic.
score >= 0.75  -> forward result to C4 for treatment
score <  0.75  -> request follow-up question
score <  0.40  -> OOD rejection
"""
OOD_THRESHOLD        = 0.40
CONFIDENCE_THRESHOLD = 0.75

def route_decision(confidence: float, is_ood: bool) -> str:
    if is_ood or confidence < OOD_THRESHOLD:
        return "ood"
    if confidence < CONFIDENCE_THRESHOLD:
        return "followup"
    return "treatment"
