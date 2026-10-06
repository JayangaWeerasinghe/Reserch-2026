from pydantic import BaseModel, Field
from typing import Literal

class QualityCheck(BaseModel):
    passed: bool
    warnings: list[str] = []
    blur_score: float
    brightness: float
    contrast: float
    edge_density: float
    resolution: str

class PredictionResponse(BaseModel):
    prediction: str
    confidence: float = Field(ge=0, le=1)
    status: Literal["known", "maybe", "unknown"]
    source: Literal["base_model", "few_shot", "fine_tuned", "quality_check", "ood"]
    quality: QualityCheck
    gradcam_image_base64: str | None = None
    message: str
    few_shot_similarity: float | None = None
    ood_score: float | None = None
    ood_method: str = "confidence-threshold fallback"
