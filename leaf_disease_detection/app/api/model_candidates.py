import logging
import os
import uuid
from datetime import datetime

import torch
import torch.nn as nn
from flask import Blueprint, g, jsonify, request
from torchvision import models as tv_models

from .deps import token_required
from training import model_retention

logger = logging.getLogger(__name__)

model_candidates_bp = Blueprint("model_candidates", __name__)


@model_candidates_bp.route("/api/expert/model-candidates/upload", methods=["POST"])
@token_required(required_role="SUPER_ADMIN")
def upload_model_candidate():
    try:
        # 1. Check file
        if "file" not in request.files:
            return jsonify({"detail": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"detail": "No selected file"}), 400

        if not (file.filename.lower().endswith(".pth")):
            return jsonify({"detail": "Only .pth files are accepted"}), 400

        # 2. Get and validate fields
        test_accuracy_raw = request.form.get("test_accuracy")
        macro_f1_raw = request.form.get("macro_f1")
        source_batch_id = request.form.get("source_batch_id") or None
        notes = request.form.get("notes") or None

        if not test_accuracy_raw or not macro_f1_raw:
            return jsonify({"detail": "Accuracy and Macro F1 are required"}), 400

        try:
            test_accuracy = float(test_accuracy_raw)
            macro_f1 = float(macro_f1_raw)
        except ValueError:
            return jsonify({"detail": "Accuracy and Macro F1 must be valid numbers"}), 400

        # Normalization rule
        if test_accuracy > 1.0:
            normalized_accuracy = test_accuracy / 100.0
        else:
            normalized_accuracy = test_accuracy

        # Create destination directory
        candidates_dir = os.path.join("models", "candidates")
        os.makedirs(candidates_dir, exist_ok=True)

        # Save temp file for validation
        candidate_uid = uuid.uuid4().hex[:8]
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"candidate_{timestamp}_{candidate_uid}.pth"
        stored_path = os.path.join(candidates_dir, safe_filename)

        file.save(stored_path)

        # 3. Model validation
        try:
            temp_model = tv_models.efficientnet_b3(weights=None)
            in_features = temp_model.classifier[1].in_features
            temp_model.classifier = nn.Sequential(
                nn.Dropout(p=0.4),
                nn.Linear(in_features, 4)
            )

            checkpoint = torch.load(stored_path, map_location="cpu", weights_only=False)
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
            elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                state_dict = checkpoint["state_dict"]
            else:
                state_dict = checkpoint

            temp_model.load_state_dict(state_dict, strict=True)

        except Exception as e:
            if os.path.exists(stored_path):
                os.remove(stored_path)
            return jsonify({"detail": f"Model architecture validation failed: {str(e)}"}), 400

        # 4. Compare model metrics
        baseline_accuracy = 0.9714
        baseline_macro_f1 = 0.9714

        if normalized_accuracy > baseline_accuracy and macro_f1 >= baseline_macro_f1:
            status = "ELIGIBLE_FOR_REVIEW"
        else:
            status = "REJECTED_BY_METRICS"

        # 5. Save candidate in database
        candidate_model_record = {
            "candidate_id": f"CAND-{timestamp}-{candidate_uid.upper()}",
            "filename": safe_filename,
            "stored_path": stored_path,
            "test_accuracy": normalized_accuracy,
            "macro_f1": macro_f1,
            "source_batch_id": source_batch_id,
            "notes": notes,
            "status": status,
            "checkpoint_pruned_at": None
        }
        g.candidate_repo.create(candidate_model_record)

        try:
            model_retention.cleanup_rejected_candidates()
        except Exception as e:
            logger.error(f"Failed to cleanup rejected candidates after upload: {e}", exc_info=True)

        accuracy_delta_pp = (normalized_accuracy - baseline_accuracy) * 100.0
        f1_delta = macro_f1 - baseline_macro_f1

        return jsonify({
            "candidate_id": candidate_model_record["candidate_id"],
            "filename": candidate_model_record["filename"],
            "test_accuracy": candidate_model_record["test_accuracy"],
            "macro_f1": candidate_model_record["macro_f1"],
            "status": candidate_model_record["status"],
            "accuracy_delta_pp": round(accuracy_delta_pp, 4),
            "f1_delta": round(f1_delta, 4),
            "decision": "Candidate Outperformed Current Model" if status == "ELIGIBLE_FOR_REVIEW" else "Candidate Rejected"
        })

    except Exception as exc:
        logger.error(f"Error uploading model candidate: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@model_candidates_bp.route("/api/expert/model-candidates", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def list_model_candidates():
    try:
        candidates = g.candidate_repo.list_all()
        result = []
        for c in candidates:
            result.append({
                "candidate_id": c.candidate_id,
                "filename": c.filename,
                "uploaded_at": c.uploaded_at.isoformat() if c.uploaded_at else None,
                "test_accuracy": c.test_accuracy,
                "macro_f1": c.macro_f1,
                "source_batch_id": c.source_batch_id,
                "notes": c.notes,
                "status": c.status,
                "checkpoint_pruned_at": c.checkpoint_pruned_at.isoformat() if getattr(c, 'checkpoint_pruned_at', None) else None
            })
        return jsonify(result)
    except Exception as exc:
        logger.error(f"Error listing model candidates: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@model_candidates_bp.route("/api/expert/model-candidates/<candidate_id>", methods=["DELETE"])
@token_required(required_role="SUPER_ADMIN")
def delete_model_candidate(candidate_id):
    try:
        candidate = g.candidate_repo.find_by_candidate_id(candidate_id)
        if not candidate:
            return jsonify({"detail": "Candidate not found"}), 404

        active_model = g.deployment_repo.find_active() if hasattr(g, 'deployment_repo') else None
        if active_model and getattr(active_model, 'checkpoint_path', None):
            active_name = os.path.basename(active_model.checkpoint_path)
            if candidate.filename and active_name and active_name == candidate.filename:
                return jsonify({"detail": "Cannot delete the currently deployed model."}), 409

        queued_or_running_jobs = []
        if hasattr(g, 'training_repo'):
            jobs = g.training_repo.list_all()
            for job in jobs:
                if job.status in ["QUEUED", "RUNNING", "PENDING", "COMPLETED", "PROMOTED"] and getattr(job, 'candidate_checkpoint', None):
                    candidate_file = os.path.basename(job.candidate_checkpoint)
                    if candidate.filename and candidate_file == candidate.filename:
                        queued_or_running_jobs.append(job.job_id)

        if queued_or_running_jobs:
            return jsonify({"detail": "Cannot delete this candidate because it is referenced by a training job."}), 409

        stored_path = getattr(candidate, 'stored_path', None)
        if stored_path and os.path.exists(stored_path):
            try:
                allowed_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "candidates")
                allowed_root = os.path.normpath(allowed_root)
                candidate_abs = os.path.normpath(stored_path)
                if os.path.commonpath([allowed_root, candidate_abs]) == allowed_root:
                    os.remove(candidate_abs)
            except Exception as exc:
                logger.warning(f"Could not remove candidate checkpoint file for {candidate_id}: {exc}")

        g.candidate_repo.collection.delete_one({"candidate_id": candidate_id})
        return jsonify({"message": "Candidate deleted successfully."})
    except Exception as exc:
        logger.error(f"Error deleting model candidate {candidate_id}: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
