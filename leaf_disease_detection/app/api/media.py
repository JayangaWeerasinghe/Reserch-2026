from flask import Blueprint, current_app, send_from_directory

media_bp = Blueprint("media", __name__)


@media_bp.route("/api/images/<filename>", methods=["GET"])
def get_image(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@media_bp.route("/api/gradcam/<filename>", methods=["GET"])
def get_gradcam_image(filename):
    return send_from_directory(current_app.config["GRADCAM_FOLDER"], filename)
