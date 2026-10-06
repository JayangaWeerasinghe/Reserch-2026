import logging
import os
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from .deps import get_top_k_candidates, token_required
from ..config import settings
from ..cloudinary_service import delete_cloudinary_asset

logger = logging.getLogger(__name__)

expert_review_bp = Blueprint("expert_review", __name__)


@expert_review_bp.route("/api/expert/review-queue", methods=["GET"])
@token_required(required_role="EXPERT")
def list_review_queue():
    try:
        low_conf_rows = g.prediction_repo.find_pending_reviews()
        top_k_rows = get_top_k_candidates()

        results = []
        for r in low_conf_rows:
            results.append({
                "case_id": r.case_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "image_name": r.image_name,
                "predicted_disease": r.predicted_disease,
                "confidence": r.confidence,
                "energy_score": r.energy_score,
                "status": r.status,
                "review_status": r.review_status,
                "review_reason": r.review_reason,
                "city": r.city if r.city else None,
                "original_image_url": r.image_url if r.image_url else (f"/api/images/{r.image_name}" if r.image_name else None),
                "gradcam_image_url": r.gradcam_url if r.gradcam_url else (f"/api/gradcam/{r.gradcam_image_name}" if r.gradcam_image_name else None)
            })

        for r in top_k_rows:
            results.append({
                "case_id": r.case_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "image_name": r.image_name,
                "predicted_disease": r.predicted_disease,
                "confidence": r.confidence,
                "energy_score": r.energy_score,
                "status": r.status,
                "review_status": r.review_status,
                "review_reason": "TOP_K_UNCERTAINTY",
                "city": r.city if r.city else None,
                "original_image_url": r.image_url if r.image_url else (f"/api/images/{r.image_name}" if r.image_name else None),
                "gradcam_image_url": r.gradcam_url if r.gradcam_url else (f"/api/gradcam/{r.gradcam_image_name}" if r.gradcam_image_name else None)
            })

        return jsonify(results)
    except Exception as exc:
        logger.error(f"Error listing review queue: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@expert_review_bp.route("/api/expert/review-queue/<case_id>", methods=["GET"])
@token_required(required_role="EXPERT")
def get_review_case(case_id):
    try:
        row = g.prediction_repo.find_by_case_id(case_id)
        if not row:
            return jsonify({"detail": "Case not found"}), 404
        return jsonify({
            "case_id": row.case_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "image_name": row.image_name,
            "predicted_disease": row.predicted_disease,
            "confidence": row.confidence,
            "energy_score": row.energy_score,
            "status": row.status,
            "review_status": row.review_status,
            "review_reason": row.review_reason,
            "expert_validated_disease": row.expert_validated_disease,
            "original_image_url": row.image_url if row.image_url else (f"/api/images/{row.image_name}" if row.image_name else None),
            "gradcam_image_url": row.gradcam_url if row.gradcam_url else (f"/api/gradcam/{row.gradcam_image_name}" if row.gradcam_image_name else None)
        })
    except Exception as exc:
        logger.error(f"Error fetching review case: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@expert_review_bp.route("/api/expert/review-queue/<case_id>/verify", methods=["PATCH", "POST"])
@token_required(required_role="EXPERT")
def verify_review_case(case_id):
    try:
        row = g.prediction_repo.find_by_case_id(case_id)
        if not row:
            return jsonify({"detail": "Case not found"}), 404

        data = request.get_json() or {}
        expert_label = data.get("expert_label")
        valid_labels = ["Bacterial_Blight", "Brown_Spot", "Healthy", "Leaf_Blast", "OOD", "Unknown"]
        if expert_label not in valid_labels:
            return jsonify({"detail": "Invalid expert label"}), 400

        needs_expert = row.needs_expert_review or False
        review_reason = row.review_reason

        if row.review_status == "pending" and not row.needs_expert_review:
            top_k = get_top_k_candidates()
            if any(c.case_id == row.case_id for c in top_k):
                needs_expert = True
                review_reason = "TOP_K_UNCERTAINTY"

        verified_at = datetime.utcnow()
        is_trainable = expert_label not in ["OOD", "Unknown"]
        updates = {
            "needs_expert_review": needs_expert,
            "review_reason": review_reason,
            "review_status": "verified",
            "expert_validated_disease": expert_label,
            "verified_at": verified_at,
            "expert_reviewed_at": verified_at,
            "approved_for_training": is_trainable,
            "consumed_by_job_id": None,
            "status": "OOD" if expert_label in ["OOD", "Unknown"] else (row.status or "KNOWN")
        }
        g.prediction_repo.update(case_id, updates)
        return jsonify({"message": "Case verified", "case_id": case_id})
    except Exception as exc:
        logger.error(f"Error verifying review case: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@expert_review_bp.route("/api/expert/review-queue/pending", methods=["DELETE"])
@token_required(required_role="SUPER_ADMIN")
def clear_pending_review_queue():
    """Bulk-clear the pending Expert Review Queue.

    Deletes ONLY the exact set of records currently shown in the queue
    (LOW_CONFIDENCE pending + top-K borderline pending) - the same union
    list_review_queue() computes. Verified, approved, consumed, candidate,
    training, and deployed-model records are never touched: they don't
    satisfy review_status == "pending" and are excluded by construction.
    """
    try:
        records = g.prediction_repo.find_review_queue_records()
        case_ids = [r.case_id for r in records]

        deleted_count = g.prediction_repo.delete_pending_review_queue_records(case_ids)

        # Best-effort Cloudinary cleanup for the removed records only,
        # skipping any asset still referenced by another remaining case.
        for r in records:
            try:
                if r.image_public_id:
                    other = g.prediction_repo.collection.find_one({
                        "image_public_id": r.image_public_id,
                        "case_id": {"$ne": r.case_id}
                    })
                    if not other:
                        delete_cloudinary_asset(r.image_public_id)
                if r.gradcam_public_id:
                    other = g.prediction_repo.collection.find_one({
                        "gradcam_public_id": r.gradcam_public_id,
                        "case_id": {"$ne": r.case_id}
                    })
                    if not other:
                        delete_cloudinary_asset(r.gradcam_public_id)
            except Exception:
                logger.warning(f"Cloudinary cleanup failed for case {r.case_id}", exc_info=True)

        return jsonify({"success": True, "deleted_count": deleted_count})
    except Exception as exc:
        logger.error(f"Error clearing pending review queue: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@expert_review_bp.route("/api/expert/dashboard-stats", methods=["GET"])
@token_required(required_role="SUPER_ADMIN")
def dashboard_stats():
    try:
        pending_count = g.prediction_repo.count_pending_expert_reviews()
        verified_count = g.prediction_repo.count_verified_expert_samples()
        approved_count = g.prediction_repo.count_approved_for_training_samples()
        active_learning_eligible_count = g.prediction_repo.count_active_learning_eligible()
        consumed_count = g.prediction_repo.count_consumed_training_samples()

        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        backups_dir = os.path.join(backend_dir, "models", "backups")
        try:
            backups_files = [f for f in os.listdir(backups_dir) if os.path.isfile(os.path.join(backups_dir, f))]
        except Exception:
            backups_files = []

        rejected_kept = g.candidate_repo.count_rejected_kept()
        active_models_count = g.deployment_repo.count_active()

        return jsonify({
            "pending_expert_reviews": pending_count,
            "verified_expert_samples": verified_count,
            "approved_for_training_samples": approved_count,
            "active_learning_eligible_samples": active_learning_eligible_count,
            "consumed_training_samples": consumed_count,
            "next_batch_size": 100,
            "storage_summary": {
                "active_models": active_models_count,
                "backups_kept": len(backups_files),
                "max_backups": settings.max_backups,
                "rejected_candidates_kept": rejected_kept,
                "max_rejected_candidates": settings.max_rejected_candidates
            }
        })
    except Exception as exc:
        logger.error(f"Error fetching dashboard stats: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
