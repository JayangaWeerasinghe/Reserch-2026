from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    app_name: str = "PaddyGuard AI - Rice Pest Detection API"
    app_version: str = "2.1.0"
    model_path: str = str(BASE_DIR / "models" / "best_model.pth")
    image_size: int = 224
    max_upload_size_mb: int = 10
    unknown_threshold: float = 0.50
    maybe_threshold: float = 0.70
    min_width: int = 224
    min_height: int = 224
    blur_threshold: float = 35.0
    min_brightness: float = 35.0
    max_brightness: float = 225.0
    min_contrast: float = 18.0
    max_edge_density: float = 0.38
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    few_shot_store_dir: str = str(BASE_DIR / "data" / "few_shot")
    few_shot_similarity_threshold: float = 0.72
    fine_tuned_store_dir: str = str(BASE_DIR / "data" / "fine_tuned")
    fine_tune_epochs: int = 8
    fine_tune_learning_rate: float = 1e-4
    fine_tune_confidence_threshold: float = 0.70
    ood_reference_path: str = str(BASE_DIR / "data" / "ood" / "reference.pt")
    ood_mahalanobis_threshold: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()
