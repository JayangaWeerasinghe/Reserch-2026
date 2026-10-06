import logging
import os
import re

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from .api import register_blueprints
from .config import settings

# Import MongoDB Repositories
from app.repositories.active_learning_repository import ActiveLearningRepository
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.deployment_repository import DeploymentRepository
from app.repositories.expert_repository import ExpertRepository
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.training_repository import TrainingRepository
from training import model_retention

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class _SuppressFineTuneStatusPolling(logging.Filter):
    """Silence noisy 200 GET access logs for fine-tune status polling only.

    The Super Admin dashboard polls /api/expert/fine-tune/status/<job_id> every
    few seconds while a job runs, which floods the terminal during live demos.
    Every other werkzeug access log line (all other routes, and any non-200
    status on this route, including 4xx/5xx) is left untouched.
    """
    _pattern = re.compile(r'"GET /api/expert/fine-tune/status/\S+ HTTP/\d\.\d" 200')

    def filter(self, record):
        return not self._pattern.search(record.getMessage())


logging.getLogger("werkzeug").addFilter(_SuppressFineTuneStatusPolling())

# Seed DeployedModelRecord in MongoDB
try:
    deployment_repo = DeploymentRepository()
    record = deployment_repo.find_active()
    if not record:
        deployment_repo.create({
            "checkpoint_path": settings.model_path,
            "test_accuracy": 0.9714,
            "macro_f1": 0.9714,
            "notes": "Seeded initial deployment (Round 2)",
            "is_active": True
        })
except Exception as e:
    logger.error(f"Failed to seed DeployedModelRecord in MongoDB: {e}")

# Optionally run a one-time cleanup on startup; non-fatal
try:
    model_retention.run_model_retention_cleanup()
except Exception as e:
    logger.error(f"Model retention startup cleanup failed: {e}")

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "uploads")
app.config['GRADCAM_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "gradcam")

# Configure CORS
# Allow all localhost ports in development, plus configured FRONTEND_ORIGIN
allowed_origins = [
    re.compile(r"^http://localhost:\d+$"),
    re.compile(r"^http://127\.0\.0\.1:\d+$"),
]
if hasattr(settings, 'frontend_origin') and settings.frontend_origin:
    allowed_origins.extend([origin.strip() for origin in settings.frontend_origin.split(',') if origin.strip()])

CORS(app, supports_credentials=True, origins=allowed_origins)


@app.after_request
def add_cors_headers(response):
    """Ensure CORS headers are present on ALL responses including errors."""
    origin = request.headers.get("Origin", "")
    if origin and ("localhost" in origin or "127.0.0.1" in origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response


@app.errorhandler(Exception)
def handle_global_exception(e):
    logger.error(f"Global unhandled exception: {e}", exc_info=True)
    response = jsonify({"detail": "An internal server error occurred. Please try again."})
    response.status_code = 500
    origin = request.headers.get("Origin", "")
    if origin and ("localhost" in origin or "127.0.0.1" in origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response


# Database repository lifecycle management
@app.before_request
def before_request():
    # Skip repo init for OPTIONS preflight — no DB needed
    if request.method == "OPTIONS":
        return
    g.prediction_repo = PredictionRepository()
    g.expert_repo = ExpertRepository()
    g.active_learning_repo = ActiveLearningRepository()
    g.candidate_repo = CandidateRepository()
    g.training_repo = TrainingRepository()
    g.deployment_repo = DeploymentRepository()


@app.teardown_appcontext
def teardown_db(exception=None):
    pass


register_blueprints(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.port, debug=True)
