"""Research-facing response schemas for the C3 pest-detection component.

The original production schemas are kept in this package as well; this file
provides the research scaffold's expected `schemas/request_schema.py` entry
point without changing the API contract used by the frontend.
"""
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


class PestDetectionResponse(BaseModel):
    pest: str
    confidence: float = Field(ge=0, le=1)
    is_ood: bool
    all_scores: dict


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


class FewShotRegisterResponse(BaseModel):
    class_name: str
    images_used: int = Field(ge=5, le=20)
    epochs: int | None = None
    fine_tuned_layers: list[str] | None = None
    message: str


class FewShotClassesResponse(BaseModel):
    classes: list[str]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    device: str
    model_name: str
