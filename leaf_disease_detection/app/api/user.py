import logging
from datetime import datetime

from flask import Blueprint, g, jsonify

from .deps import token_required
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

user_bp = Blueprint("user", __name__)


@user_bp.route("/api/user/me", methods=["GET"])
@token_required()
def user_me():
    try:
        user_id = g.current_user.get("user_id")
        role = g.current_user.get("role")

        if role == "USER":
            user = UserRepository().find_by_id(user_id)
            if not user:
                return jsonify({"detail": "User not found"}), 404
            return jsonify({
                "user_id": user.user_id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active
            })
        elif role == "EXPERT":
            user = g.expert_repo.find_by_id(user_id)
            if not user:
                return jsonify({"detail": "Expert not found"}), 404
            return jsonify({
                "user_id": str(user.id),
                "name": user.name,
                "email": user.username,
                "role": user.role,
                "is_active": user.is_active
            })
        elif role == "SUPER_ADMIN":
            return jsonify({
                "user_id": "SUPER_ADMIN",
                "name": "Super Admin",
                "email": "admin@paddyguard.com",
                "role": "SUPER_ADMIN",
                "is_active": True
            })
        else:
            return jsonify({"detail": "Invalid role"}), 400
    except Exception as exc:
        logger.error(f"Error in /api/user/me: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500


@user_bp.route("/api/user/history", methods=["GET"])
@token_required(required_role="USER")
def user_history():
    try:
        user_id = g.current_user["user_id"]
        cursor = g.prediction_repo.collection.find({"user_id": str(user_id)}).sort("created_at", -1)
        results = []
        for r in cursor:
            results.append({
                "case_id": r.get("case_id"),
                "created_at": r.get("created_at").isoformat() if isinstance(r.get("created_at"), datetime) else r.get("created_at"),
                "predicted_disease": r.get("predicted_disease"),
                "confidence": r.get("confidence"),
                "severity_percentage": r.get("severity_percentage"),
                "severity_level": r.get("severity_level"),
                "status": r.get("status"),
                "city": r.get("city"),
                "district": r.get("district"),
                "field_area_acres": r.get("field_area_acres"),
                "affected_field_percentage": r.get("affected_field_percentage"),
                "rice_variety": r.get("rice_variety"),
                "growth_stage": r.get("growth_stage"),
                "expected_yield_kg_per_acre": r.get("expected_yield_kg_per_acre"),
                "treatment_applied": r.get("treatment_applied"),
                "original_image_url": r.get("image_url") if r.get("image_url") else (f"/api/images/{r.get('image_name')}" if r.get("image_name") else None),
                "gradcam_image_url": r.get("gradcam_url") if r.get("gradcam_url") else (f"/api/gradcam/{r.get('gradcam_image_name')}" if r.get("gradcam_image_name") else None)
            })
        return jsonify(results)
    except Exception as exc:
        logger.error(f"Error in user_history: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
