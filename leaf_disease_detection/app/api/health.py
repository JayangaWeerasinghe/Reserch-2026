from flask import Blueprint, jsonify

from ..ml_service import model_service

health_bp = Blueprint("health", __name__)


@health_bp.route("/", methods=["GET"])
def root():
    return jsonify({"message": "PaddyGuard AI API is running", "docs": "/docs"})


@health_bp.route("/api/health", methods=["GET"])
@health_bp.route("/health", methods=["GET"])
def health():
    try:
        from app.database import get_mongo_client
        client = get_mongo_client()
        # The ismaster command is cheap and does not require auth.
        client.admin.command('ismaster')
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return jsonify({
        "status": "ok",
        "database": db_status,
        "model_loaded": model_service.model is not None
    })
