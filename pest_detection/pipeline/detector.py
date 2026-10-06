"""PaddyGuard AI pest-detection pipeline facade.

This module keeps the research project's expected `pipeline.detector` entry
point while delegating the actual working implementation to the existing
DenseNet121 prediction stack. No ML behaviour is reimplemented here.
"""
from functools import lru_cache
from PIL import Image

from pipeline.core.config import Settings, get_settings
from pipeline.ml.model_loader import DenseNet121Classifier
from pipeline.services.image_quality import ImageQualityService
from pipeline.services.prediction_service import PredictionService


@lru_cache(maxsize=1)
def get_service() -> PredictionService:
    settings = get_settings()
    classifier = DenseNet121Classifier(settings)
    return PredictionService(
        settings,
        classifier,
        ImageQualityService(settings),
    )


def load_model() -> PredictionService:
    """Initialize and return the cached PaddyGuard detection service."""
    return get_service()


def detect_with_ood(pil_image: Image.Image) -> dict:
    """Run the complete PaddyGuard pipeline on one PIL image.

    The function name is retained for compatibility with the research
    structure, while the implementation includes quality checking, DenseNet
    prediction, Mahalanobis OOD, few-shot learning, selective fine-tuning,
    and Grad-CAM explainability.
    """
    return get_service().predict(pil_image)
