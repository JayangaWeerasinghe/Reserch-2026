"""
C1 API endpoints: /diagnose and /followup
Owner: Jayonga Weerasinghe (IT22273680)

Novelties added in this version:
  Novelty 2: Audio quality gate before ASR
  Novelty 3: Confidence trajectory tracking across follow-up questions
  Novelty 4: Sinhala TTS voice output returned in response
  Novelty 5: Symptom severity scoring added to response
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from pipeline.asr import transcribe_audio, ASRError, get_asr_provider
from pipeline.translator import translate_to_english
from pipeline.classifier import classify_with_ood
from pipeline.followup import get_followup_question, resolve_answer
from pipeline.session_store import (
    create_session,
    get_session,
    update_session,
    delete_session,
    append_trajectory,
)
# ── 4 novelty imports ─────────────────────────────────────────────────────────
from pipeline.audio_quality import check_audio_quality      # Novelty 2
from pipeline.severity_scorer import score_severity         # Novelty 5
from pipeline.tts import synthesise_result, synthesise_question  # Novelty 4

import tempfile, os, logging

logger = logging.getLogger("voice_nlp.endpoints")
router = APIRouter()
MAX_FOLLOWUP_QUESTIONS = 3


class FollowUpRequest(BaseModel):
    answer: str
    session_id: str


def _save_temp_audio(audio_bytes: bytes, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        return tmp.name


def _cleanup(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


def _with_asr_metadata(payload: dict) -> dict:
    provider = get_asr_provider()
    payload["asr_backend"] = provider.backend
    payload["asr_model"] = getattr(provider, "model_name", "unknown")
    return payload


@router.post("/diagnose")
async def diagnose(audio: UploadFile = File(...)):
    """
    Full pipeline with 4 novelties integrated:

    1. Audio Quality Gate   (Novelty 2) — validate before ASR
    2. ASR                             — Sinhala text
    3. Translation                     — English text
    4. Severity Scoring    (Novelty 5) — mild/moderate/severe from language
    5. Classify + OOD                  — disease + confidence
    6. TTS Output          (Novelty 4) — Sinhala speech audio
    7. Session + Trajectory (Novelty 3) — track confidence across follow-ups
    """

    # ── Validate content type ──────────────────────────────────────────
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail=f"ගොනුව ශ්‍රව්‍ය ගොනුවක් විය යුතුය. ලැබුණේ: {audio.content_type}"
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=400,
            detail="ශ්‍රව්‍ය ගොනුව හිස්ය. නැවත උත්සාහ කරන්න."
        )

    suffix   = os.path.splitext(audio.filename or "")[1] or ".ogg"
    tmp_path = _save_temp_audio(audio_bytes, suffix)

    try:
        # ─────────────────────────────────────────────────────────────────
        # NOVELTY 2: Audio Quality Gate
        # Check signal quality BEFORE sending to Whisper
        # Prevents hallucination from silent/clipped/noisy recordings
        # ─────────────────────────────────────────────────────────────────
        quality = check_audio_quality(tmp_path)
        logger.info(
            "Audio quality: passed=%s snr=%s silence=%s duration=%s",
            quality.passed, quality.snr, quality.silence_ratio, quality.duration
        )
        if not quality.passed:
                return _with_asr_metadata({
                    "disease"           : "Unknown / OOD",
                    "label_id"          : -1,
                    "confidence"        : 0.0,
                    "is_ood"            : True,
                    "ood_reason"        : "audio_quality",
                    "needs_followup"    : False,
                    "status"            : "Audio quality check failed",
                    "message"           : quality.reason,
                    "message_en"        : quality.reason_en,
                    "all_scores"        : {},
                    "sinhala_transcript": None,
                    "english_translation": None,
                    "session_id"        : None,
                    "followup_question" : None,
                    "followup_question_en": None,
                    "tts_audio_b64"     : None,   # Novelty 4
                    "severity"          : None,   # Novelty 5
                    "confidence_trajectory": [],  # Novelty 3
                    "audio_quality"     : quality.to_dict(),  # Novelty 2
                })
        # ── ASR: audio → Sinhala text ──────────────────────────────────
        logger.info("ASR: transcribing audio (%d bytes)...", len(audio_bytes))
        sinhala_text = transcribe_audio(tmp_path)
        if not sinhala_text or not sinhala_text.strip():
            raise HTTPException(
                status_code=400,
                detail="හඬ හඳුනා ගත නොහැකි විය. කරුණාකර පැහැදිලිව කතා කර නැවත උත්සාහ කරන්න."
            )
        logger.info("ASR transcription complete")

        # ── Translate: Sinhala → English ───────────────────────────────
        english_text = translate_to_english(sinhala_text)
        logger.info("Translation: %s", english_text)

        # ─────────────────────────────────────────────────────────────────
        # NOVELTY 5: Severity Scoring
        # Score infection severity from language intensity
        # Runs on both Sinhala + English for maximum signal coverage
        # ─────────────────────────────────────────────────────────────────
        severity = score_severity(sinhala_text, english_text)
        logger.info("Severity: %s", severity)

        # ── Classify + OOD check ───────────────────────────────────────
        result = classify_with_ood(english_text)
        logger.info(
            "Classification: %s  conf=%.3f  ood=%s  followup=%s",
            result["disease"], result["confidence"],
            result["is_ood"], result["needs_followup"]
        )

        # ─────────────────────────────────────────────────────────────────
        # NOVELTY 4: TTS — synthesise Sinhala speech for the result
        # ─────────────────────────────────────────────────────────────────
        tts_audio = synthesise_result(
            disease        = result["disease"],
            confidence     = result["confidence"],
            needs_followup = result["needs_followup"],
            is_ood         = result["is_ood"],
            severity       = severity if not result["is_ood"] else None,
        )

        # ─────────────────────────────────────────────────────────────────
        # NOVELTY 3: Confidence trajectory — initialised in create_session
        # ─────────────────────────────────────────────────────────────────
        if result["needs_followup"] and not result["is_ood"]:
            session_id    = create_session(
                disease    = result["disease"],
                confidence = result["confidence"],
            )
            question_dict = get_followup_question(
                disease_prediction = result["disease"],
                question_index     = 0,
            )
            update_session(session_id, {
                "disease"               : result["disease"],
                "original_disease"      : result["disease"],
                "confidence"            : result["confidence"],
                "question_index"        : 0,
                "answers"               : [],
                "question_dict"         : question_dict,
                "confidence_trajectory" : [
                    {
                        "step"      : 0,
                        "label"     : "Initial",
                        "disease"   : result["disease"],
                        "confidence": round(result["confidence"], 3),
                    }
                ],
            })

            # TTS for the follow-up question (Novelty 4)
            question_tts = synthesise_question(question_dict["sinhala"])

            return _with_asr_metadata({
                **result,
                "sinhala_transcript"    : sinhala_text,
                "english_translation"   : english_text,
                "session_id"            : session_id,
                "followup_question"     : question_dict["sinhala"],
                "followup_question_en"  : question_dict["english"],
                "question_number"       : 1,
                "max_questions"         : MAX_FOLLOWUP_QUESTIONS,
                # Novelties
                "tts_audio_b64"         : tts_audio,        # Novelty 4
                "question_tts_b64"      : question_tts,     # Novelty 4
                "severity"              : severity,          # Novelty 5
                "confidence_trajectory" : [                  # Novelty 3
                    {
                        "step"      : 0,
                        "label"     : "Initial",
                        "disease"   : result["disease"],
                        "confidence": round(result["confidence"], 3),
                    }
                ],
                "audio_quality"         : quality.to_dict(),# Novelty 2
            })

        # Confident or OOD result
        return _with_asr_metadata({
            **result,
            "sinhala_transcript"    : sinhala_text,
            "english_translation"   : english_text,
            "session_id"            : None,
            "followup_question"     : None,
            "followup_question_en"  : None,
            # Novelties
            "tts_audio_b64"         : tts_audio,    # Novelty 4
            "question_tts_b64"      : None,
            "severity"              : severity if not result["is_ood"] else None,  # Novelty 5
            "confidence_trajectory" : [],            # Novelty 3 — no session
            "audio_quality"         : quality.to_dict(),  # Novelty 2
        })

    except ASRError as e:
        logger.warning("ASR request failed: %s", str(e))
        raise HTTPException(status_code=e.status_code, detail=str(e)) from None
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Pipeline error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"රෝග විනිශ්චය අසාර්ථක විය: {str(e)}"
        )
    finally:
        _cleanup(tmp_path)


@router.post("/followup")
async def followup(req: FollowUpRequest):
    """
    Accept farmer follow-up answer.
    Novelty 3: Appends each step to confidence_trajectory.
    Novelty 4: Returns TTS for next question and final result.
    """
    session = get_session(req.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="සැසිය හමු නොවීය හෝ කල් ඉකුත් විය. නව රෝග විනිශ්චයක් ආරම්භ කරන්න."
        )

    question_index    = session.get("question_index", 0)
    answers           = session.get("answers", [])
    question_dict     = session.get("question_dict", {})
    trajectory        = session.get("confidence_trajectory", [])
    original_disease  = session.get("original_disease", session.get("disease"))

    if question_index >= MAX_FOLLOWUP_QUESTIONS:
        delete_session(req.session_id)
        raise HTTPException(
            status_code=400,
            detail="උපරිම ප්‍රශ්න ගණන ඉක්මවා ඇත. නව රෝග විනිශ්චයක් ආරම්භ කරන්න."
        )

    english_answer = resolve_answer(req.answer, question_dict)
    is_no_answer   = bool(question_dict.get("no_hint")) and english_answer == question_dict.get("no_hint")
    logger.info("Follow-up Q%d raw='%s' resolved='%s' is_no=%s",
                question_index+1, req.answer, english_answer, is_no_answer)

    answers.append(req.answer.strip())
    next_index = question_index + 1
    result     = classify_with_ood(english_answer)

    # ─────────────────────────────────────────────────────────────────────
    # NOVELTY 3: Append this step to confidence trajectory
    # ─────────────────────────────────────────────────────────────────────
    trajectory.append({
        "step"      : next_index,
        "label"     : f"Q{next_index} — {req.answer[:20]}",
        "disease"   : result["disease"],
        "confidence": round(result["confidence"], 3),
    })

    logger.info("Follow-up Q%d result: %s conf=%.3f",
                next_index, result["disease"], result["confidence"])

    still_unsure   = result["needs_followup"] and not result["is_ood"]
    questions_left = next_index < MAX_FOLLOWUP_QUESTIONS

    # If the farmer answered "No", keep working through this disease's
    # question bank instead of concluding early (e.g. jumping straight to
    # "Healthy" off one "No"). Only finalise once every question for the
    # originally suspected disease has been asked.
    keep_asking = questions_left and (still_unsure or is_no_answer)

    if keep_asking:
        next_question_dict = get_followup_question(
            disease_prediction = original_disease,
            question_index     = next_index,
        )
        update_session(req.session_id, {
            "disease"               : result["disease"],
            "original_disease"      : original_disease,
            "confidence"            : result["confidence"],
            "question_index"        : next_index,
            "answers"               : answers,
            "question_dict"         : next_question_dict,
            "confidence_trajectory" : trajectory,   # Novelty 3
        })

        # Novelty 4: TTS for next question
        question_tts = synthesise_question(next_question_dict["sinhala"])

        return {
            **result,
            "session_id"            : req.session_id,
            "followup_question"     : next_question_dict["sinhala"],
            "followup_question_en"  : next_question_dict["english"],
            "question_number"       : next_index + 1,
            "max_questions"         : MAX_FOLLOWUP_QUESTIONS,
            "tts_audio_b64"         : None,
            "question_tts_b64"      : question_tts,       # Novelty 4
            "confidence_trajectory" : trajectory,          # Novelty 3
            "severity"              : None,
        }

    # Final result
    delete_session(req.session_id)
    logger.info("Follow-up complete after %d Q(s). Final: %s conf=%.3f",
                next_index, result["disease"], result["confidence"])

    # Novelty 5: severity on final result
    severity = score_severity("", english_answer)

    # Novelty 4: TTS for final result
    tts_audio = synthesise_result(
        disease        = result["disease"],
        confidence     = result["confidence"],
        needs_followup = False,
        is_ood         = result["is_ood"],
        severity       = severity,
    )

    return {
        **result,
        "session_id"            : None,
        "followup_question"     : None,
        "followup_question_en"  : None,
        "question_number"       : next_index,
        "max_questions"         : MAX_FOLLOWUP_QUESTIONS,
        "followup_complete"     : True,
        "tts_audio_b64"         : tts_audio,      # Novelty 4
        "question_tts_b64"      : None,
        "confidence_trajectory" : trajectory,      # Novelty 3
        "severity"              : severity,         # Novelty 5
    }
