import base64
import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from io import BytesIO

from flask import Blueprint, current_app, g, jsonify, request
from PIL import Image

from .deps import verify_token_details
from ..cloudinary_service import upload_image_to_cloudinary
from ..ml_service import model_service
from ..risk import calculate_risk, severity_label
from ..weather import geocode_sri_lanka, get_weather

logger = logging.getLogger(__name__)

analyze_bp = Blueprint("analyze", __name__)


@analyze_bp.route("/api/analyze", methods=["POST"])
def analyze():
    if 'file' not in request.files:
        return jsonify({"detail": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"detail": "No selected file"}), 400

    # Parse form parameters
    city = request.form.get("city", "").strip()

    try:
        latitude_str = request.form.get("latitude")
        latitude = float(latitude_str) if latitude_str and latitude_str.lower() != 'none' else None
    except ValueError:
        latitude = None

    try:
        longitude_str = request.form.get("longitude")
        longitude = float(longitude_str) if longitude_str and longitude_str.lower() != 'none' else None
    except ValueError:
        longitude = None

    try:
        field_area_acres = float(request.form.get("field_area_acres", 0))
    except ValueError:
        return jsonify({"detail": "Field area must be a valid number"}), 400

    try:
        affected_field_percentage = float(request.form.get("affected_field_percentage", 0))
    except ValueError:
        return jsonify({"detail": "Affected field percentage must be a valid number"}), 400

    rice_variety = request.form.get("rice_variety", "Unknown")
    growth_stage = request.form.get("growth_stage", "Unknown")

    try:
        expected_yield_str = request.form.get("expected_yield_kg_per_acre")
        expected_yield_kg_per_acre = float(expected_yield_str) if expected_yield_str and expected_yield_str.lower() != 'none' else None
    except ValueError:
        expected_yield_kg_per_acre = None

    treatment_applied_str = request.form.get("treatment_applied", "false").lower()
    treatment_applied = treatment_applied_str in ["true", "1", "yes"]

    # Validations
    if field_area_acres <= 0:
        return jsonify({"detail": "Field area must be greater than zero"}), 400
    if not 0 <= affected_field_percentage <= 100:
        return jsonify({"detail": "Affected field percentage must be between 0 and 100"}), 400

    try:
        # Read image bytes and calculate SHA-256 hash
        image_bytes = file.read()
        image_hash = hashlib.sha256(image_bytes).hexdigest()

        # Optional Token Extraction & Verification
        token = None
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        user_info = None
        if token:
            user_info, _, _ = verify_token_details(token)

        # Duplicate detection (only for authenticated normal users)
        if user_info and user_info.get("role") == "USER":
            user_id = user_info.get("user_id")
            five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
            duplicate_case = g.prediction_repo.collection.find_one({
                "user_id": str(user_id),
                "image_hash": image_hash,
                "created_at": {"$gte": five_minutes_ago}
            })
            if duplicate_case:
                elapsed = (datetime.utcnow() - duplicate_case["created_at"]).total_seconds()
                retry_after_seconds = max(0, int(300 - elapsed))
                return jsonify({
                    "error": "duplicate_upload",
                    "message": "You already uploaded this same image within the last 5 minutes.",
                    "retry_after_seconds": retry_after_seconds
                }), 429

        case_id = f"PG-{uuid.uuid4().hex[:12].upper()}"
        ext = os.path.splitext(file.filename)[1]
        if not ext:
            ext = ".jpg"
        stored_filename = f"{case_id}{ext}"

        # Temporarily save original image for ML and Cloudinary upload
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        temp_original_path = os.path.join(current_app.config['UPLOAD_FOLDER'], stored_filename)
        with open(temp_original_path, "wb") as f:
            f.write(image_bytes)

        image = Image.open(BytesIO(image_bytes))
        prediction = model_service.predict(image)

        # Clean up local original temp file if image is OOD
        if prediction["status"] == "OOD":
            try:
                os.remove(temp_original_path)
            except Exception:
                pass
            return jsonify({"prediction": prediction, "context_analysis": None})

        # Upload original image to Cloudinary
        original_upload = upload_image_to_cloudinary(temp_original_path, "paddyguard/originals")
        image_url = original_upload["secure_url"]
        image_public_id = original_upload["public_id"]

        # Clean up local original copy now that it's in Cloudinary
        try:
            os.remove(temp_original_path)
        except Exception as e:
            logger.error(f"Failed to delete temp original file: {e}")

        # Process Grad-CAM visualization
        gradcam_image_name = None
        gradcam_url = None
        gradcam_public_id = None
        if prediction.get("gradcam_base64"):
            gradcam_image_name = f"{case_id}.png"
            os.makedirs(current_app.config['GRADCAM_FOLDER'], exist_ok=True)
            temp_gradcam_path = os.path.join(current_app.config['GRADCAM_FOLDER'], gradcam_image_name)
            gradcam_bytes = base64.b64decode(prediction["gradcam_base64"])
            with open(temp_gradcam_path, "wb") as f:
                f.write(gradcam_bytes)

            # Upload Grad-CAM to Cloudinary
            gradcam_upload = upload_image_to_cloudinary(temp_gradcam_path, "paddyguard/gradcam")
            gradcam_url = gradcam_upload["secure_url"]
            gradcam_public_id = gradcam_upload["public_id"]

            # Clean up local Grad-CAM copy
            try:
                os.remove(temp_gradcam_path)
            except Exception as e:
                logger.error(f"Failed to delete temp gradcam file: {e}")

        # Location and Weather Analysis
        if latitude is None or longitude is None:
            if not city:
                return jsonify({"detail": "Provide a Sri Lankan city or GPS coordinates"}), 400
            location = geocode_sri_lanka(city)
        else:
            location = {
                "city": city or "GPS location",
                "district": None,
                "latitude": latitude,
                "longitude": longitude,
            }

        weather = get_weather(location["latitude"], location["longitude"])

        if prediction["status"] == "KNOWN":
            risk = calculate_risk(
                disease=prediction["prediction"],
                severity_percentage=prediction["severity_percentage"],
                affected_field_percentage=affected_field_percentage,
                growth_stage=growth_stage,
                weather=weather,
                area_acres=field_area_acres,
                expected_yield_kg_per_acre=expected_yield_kg_per_acre,
                treatment_applied=treatment_applied,
            )
            calc_breakdown = risk.pop("calculation_breakdown", {})
            calc_breakdown["disease"] = {
                "predicted_class": prediction["prediction"],
                "confidence": prediction["confidence"],
                "class_probabilities": prediction.get("class_probabilities", {})
            }
            severity_breakdown = prediction.get("severity_breakdown", {})
            calc_breakdown["severity"] = {
                "method": prediction.get("severity_method"),
                "activation_threshold": severity_breakdown.get("activation_threshold"),
                "active_pixel_count": severity_breakdown.get("active_pixel_count"),
                "total_pixel_count": severity_breakdown.get("total_pixel_count"),
                "severity_percentage": prediction["severity_percentage"],
                "severity_level": severity_label(prediction["severity_percentage"]) if prediction["severity_percentage"] is not None else None
            }
        else:
            risk = {}
            calc_breakdown = None

        username_from_request = request.form.get("created_by") or request.headers.get("X-User-Name")
        current_user = getattr(g, "current_user", None) or {}
        created_by = username_from_request or current_user.get("username")

        final_user_id = user_info.get("user_id") if user_info else None

        record_data = {
            "case_id": case_id,
            "user_id": final_user_id,
            "image_hash": image_hash,
            "image_name": stored_filename,
            "image_url": image_url,
            "image_public_id": image_public_id,
            "gradcam_image_name": gradcam_image_name,
            "gradcam_url": gradcam_url,
            "gradcam_public_id": gradcam_public_id,
            "predicted_disease": prediction["prediction"],
            "confidence": prediction["confidence"],
            "status": prediction["status"],
            "severity_percentage": prediction.get("severity_percentage"),
            "severity_level": severity_label(prediction["severity_percentage"]) if prediction.get("severity_percentage") is not None else None,
            "city": location["city"],
            "district": location.get("district"),
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "field_area_acres": field_area_acres,
            "affected_field_percentage": affected_field_percentage,
            "rice_variety": rice_variety,
            "growth_stage": growth_stage,
            "expected_yield_kg_per_acre": expected_yield_kg_per_acre,
            "treatment_applied": treatment_applied,
            "weather_json": json.dumps(weather),
            "predicted_loss_percentage": risk.get("predicted_loss_percentage"),
            "estimated_loss_kg": risk.get("estimated_loss_kg"),
            "created_by": created_by,
            "is_low_confidence": prediction.get("is_low_confidence", False),
            "energy_score": prediction.get("energy_score"),
            "needs_expert_review": prediction.get("needs_expert_review", False),
            "review_status": "pending",
            "review_reason": "LOW_CONFIDENCE" if prediction.get("needs_expert_review", False) else None,
            "consumed_by_job_id": None,
            "approved_for_training": False
        }

        g.prediction_repo.create(record_data)

        return jsonify({
            "case_id": case_id,
            "prediction": prediction,
            "severity_level": record_data["severity_level"],
            "location": location,
            "weather": weather,
            "yield_loss": risk if prediction["status"] == "KNOWN" else None,
            "calculation_breakdown": calc_breakdown,
            "advisory": {
                "message": "Use this result as decision support and confirm severe/uncertain cases with an agricultural officer." if prediction["status"] == "KNOWN" else "This prediction is uncertain. An expert review has been requested.",
                "safety": "Do not apply chemical treatment based only on an AI result.",
            },
        })
    except ValueError as exc:
        logger.error(f"Validation/Geocoding error: {exc}")
        return jsonify({"detail": str(exc)}), 400
    except Exception as exc:
        logger.error(f"Unhandled error in analyze: {exc}", exc_info=True)
        return jsonify({"detail": str(exc)}), 500
