import os
from pathlib import Path

# Load environment variables from backend/.env if python-dotenv is installed.
# This resolves the file relative to the backend directory instead of the shell CWD.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

class Settings:
    def __init__(self):
        try:
            self.port = int(os.getenv("PORT", "8000"))
        except ValueError:
            self.port = 8000

        self.model_path = os.getenv("MODEL_PATH", "models/PaddyGuard_active_learning_round2.pth")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./data/paddyguard.db")
        self.frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

        # MongoDB and Cloudinary settings: must come from environment only
        self.mongodb_uri = (os.getenv("MONGODB_URI") or "").strip()
        self.cloudinary_cloud_name = (os.getenv("CLOUDINARY_CLOUD_NAME") or "").strip()
        self.cloudinary_api_key = (os.getenv("CLOUDINARY_API_KEY") or "").strip()
        self.cloudinary_api_secret = (os.getenv("CLOUDINARY_API_SECRET") or "").strip()

        self.validate_required_settings()

    def validate_required_settings(self):
        missing = []
        if not self.mongodb_uri:
            missing.append("MONGODB_URI")
        if not self.cloudinary_cloud_name:
            missing.append("CLOUDINARY_CLOUD_NAME")
        if not self.cloudinary_api_key:
            missing.append("CLOUDINARY_API_KEY")
        if not self.cloudinary_api_secret:
            missing.append("CLOUDINARY_API_SECRET")
        if not (os.getenv("SUPER_ADMIN_USERNAME") or "").strip():
            missing.append("SUPER_ADMIN_USERNAME")
        if not (os.getenv("SUPER_ADMIN_PASSWORD") or "").strip():
            missing.append("SUPER_ADMIN_PASSWORD")
        if not (os.getenv("SECRET_KEY") or "").strip():
            missing.append("SECRET_KEY")
        if missing:
            print(f"WARNING: PaddyGuard config is missing required variables: {', '.join(missing)}")

        try:
            self.ood_energy_threshold = float(os.getenv("OOD_ENERGY_THRESHOLD", "5.0"))
        except ValueError:
            self.ood_energy_threshold = 5.0
            
        try:
            self.uncertain_threshold = float(os.getenv("UNCERTAIN_THRESHOLD", "0.70"))
        except ValueError:
            self.uncertain_threshold = 0.70
            
        try:
            self.low_confidence_threshold = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.50"))
        except ValueError:
            self.low_confidence_threshold = 0.50

        self.super_admin_username = (os.getenv("SUPER_ADMIN_USERNAME") or "").strip()
        self.super_admin_password = (os.getenv("SUPER_ADMIN_PASSWORD") or "").strip()
        self.secret_key = (os.getenv("SECRET_KEY") or "").strip()
        try:
            self.auth_token_max_age_seconds = int(os.getenv("AUTH_TOKEN_MAX_AGE_SECONDS", "28800"))
        except ValueError:
            self.auth_token_max_age_seconds = 28800

        try:
            self.min_fine_tune_samples = int(os.getenv("MIN_FINE_TUNE_SAMPLES", "3"))
        except ValueError:
            self.min_fine_tune_samples = 3

        try:
            self.fine_tune_epochs = int(os.getenv("FINE_TUNE_EPOCHS", "3"))
        except ValueError:
            self.fine_tune_epochs = 3

        self.test_dataset_path = os.getenv("TEST_DATASET_PATH", "data/test_dataset")
        try:
            self.max_rejected_candidates = int(os.getenv("MAX_REJECTED_CANDIDATES", "3"))
        except ValueError:
            self.max_rejected_candidates = 3

        try:
            self.max_backups = int(os.getenv("MAX_BACKUPS", "2"))
        except ValueError:
            self.max_backups = 2

        try:
            self.training_log_retention_days = int(os.getenv("TRAINING_LOG_RETENTION_DAYS", "14"))
        except ValueError:
            self.training_log_retention_days = 14

settings = Settings()
