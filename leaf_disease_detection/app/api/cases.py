import json
import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from .deps import get_top_k_candidates
from ..cloudinary_service import delete_cloudinary_asset
from ..risk import calculate_risk
from ..weather import get_weather

logger = logging.getLogger(__name__)

cases_bp = Blueprint("cases", __name__)


@cases_bp.route("/api/cases", methods=["GET"])
def list_cases():
    try:
        username = request.args.get("username")
        current_user = getattr(g, "current_user", None) or {}
        requested_username = username or current_user.get("username")

        top_k_rows = get_top_k_candidates()
        top_k_ids = {r.case_id for r in top_k_rows}

        rows = g.prediction_repo.collection.find({}) if not requested_username else g.prediction_repo.collection.find({"created_by": requested_username})
        rows = rows.sort("created_at", -1)
        results = []
        for r in rows:
            needs_expert = r.get("needs_expert_review")
            rev_reason = r.get("review_reason")
            if r.get("case_id") in top_k_ids:
                needs_expert = True
                rev_reason = "TOP_K_UNCERTAINTY"

            results.append({
                "case_id": r.get("case_id"),
                "created_at": r.get("created_at").isoformat() if isinstance(r.get("created_at"), datetime) else r.get("created_at"),
                "predicted_disease": r.get("predicted_disease"),
                "confidence": r.get("confidence"),
                "severity_percentage": r.get("severity_percentage"),
                "severity_level": r.get("severity_level"),
                "city": r.get("city"),
                "predicted_loss_percentage": r.get("predicted_loss_percentage"),
                "estimated_loss_kg": r.get("estimated_loss_kg"),
                "approved_for_training": r.get("approved_for_training"),
                "needs_expert_review": needs_expert,
                "review_status": r.get("review_status"),
                "review_reason": rev_reason,
                "expert_validated_disease": r.get("expert_validated_disease"),
                "created_by": r.get("created_by"),
                "original_image_url": r.get("image_url") if r.get("image_url") else (f"/api/images/{r.get('image_name')}" if r.get("image_name") else None),
                "gradcam_image_url": r.get("gradcam_url") if r.get("gradcam_url") else (f"/api/gradcam/{r.get('gradcam_image_name')}" if r.get("gradcam_image_name") else None)
            })
        return jsonify(results)
    except Exception as exc:
        logger.error(f"Error listing cases: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@cases_bp.route("/api/cases/<case_id>", methods=["DELETE"])
def delete_case(case_id):
    try:
        row = g.prediction_repo.find_by_case_id(case_id)
        if not row:
            return jsonify({"detail": "Case not found"}), 404

        # Clean up Cloudinary assets associated with this case (if no other case uses them)
        if row.image_public_id:
            other = g.prediction_repo.collection.find_one({"image_public_id": row.image_public_id, "case_id": {"$ne": case_id}})
            if not other:
                delete_cloudinary_asset(row.image_public_id)
        if row.gradcam_public_id:
            other = g.prediction_repo.collection.find_one({"gradcam_public_id": row.gradcam_public_id, "case_id": {"$ne": case_id}})
            if not other:
                delete_cloudinary_asset(row.gradcam_public_id)

        g.prediction_repo.delete(case_id)
        return jsonify({"message": "Case deleted successfully"})
    except Exception as exc:
        logger.error(f"Error deleting case: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@cases_bp.route("/api/cases/<case_id>/feedback", methods=["PATCH"])
def update_feedback(case_id):
    try:
        row = g.prediction_repo.find_by_case_id(case_id)
        if not row:
            return jsonify({"detail": "Case not found"}), 404

        data = request.get_json() or {}
        allowed_fields = [
            "farmer_confirmation",
            "expert_validated_disease",
            "actual_harvest_kg",
            "expected_healthy_harvest_kg",
            "approved_for_training"
        ]
        updates = {}
        for key in allowed_fields:
            if key in data:
                updates[key] = data[key]

        g.prediction_repo.update(case_id, updates)
        return jsonify({"message": "Feedback saved", "case_id": case_id})
    except Exception as exc:
        logger.error(f"Error updating feedback: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@cases_bp.route("/api/cases/<case_id>/refresh-weather", methods=["POST"])
def refresh_weather(case_id):
    try:
        row = g.prediction_repo.find_by_case_id(case_id)
        if not row:
            return jsonify({"detail": "Case not found"}), 404

        if row.latitude is None or row.longitude is None:
            return jsonify({"detail": "Case lacks GPS coordinates for weather refresh"}), 400

        weather = get_weather(row.latitude, row.longitude)

        risk = calculate_risk(
            disease=row.predicted_disease,
            severity_percentage=row.severity_percentage,
            affected_field_percentage=row.affected_field_percentage,
            growth_stage=row.growth_stage,
            weather=weather,
            area_acres=row.field_area_acres,
            expected_yield_kg_per_acre=row.expected_yield_kg_per_acre,
            treatment_applied=row.treatment_applied,
        )

        updates = {
            "weather_json": json.dumps(weather),
            "predicted_loss_percentage": risk["predicted_loss_percentage"],
            "estimated_loss_kg": risk.get("estimated_loss_kg")
        }
        g.prediction_repo.update(case_id, updates)

        calc_breakdown = risk.pop("calculation_breakdown", {})

        return jsonify({
            "message": "Weather refreshed",
            "weather": weather,
            "yield_loss": risk,
            "calculation_breakdown": calc_breakdown
        })
    except Exception as exc:
        logger.error(f"Error refreshing weather: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
