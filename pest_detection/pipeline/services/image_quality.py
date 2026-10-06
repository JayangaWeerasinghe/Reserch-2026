import cv2
import numpy as np
from PIL import Image
from pipeline.core.config import Settings
from schemas.prediction import QualityCheck

class ImageQualityService:
    """Fast, explainable image usability checks before ML inference.

    These are quality heuristics, not a pest detector. Pest-size/visibility is
    approximated through visual-content checks; a dedicated object detector can
    replace this layer later without changing the API contract.
    """
    def __init__(self, settings: Settings):
        self.s = settings

    def evaluate(self, image: Image.Image) -> QualityCheck:
        rgb = np.array(image.convert("RGB"))
        h, w = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        contrast = float(gray.std())
        edges = cv2.Canny(gray, 100, 200)
        edge_density = float(np.mean(edges > 0))

        warnings: list[str] = []
        if w < self.s.min_width or h < self.s.min_height:
            warnings.append("Image resolution is too low. Please capture a higher-resolution image.")
        if blur < self.s.blur_threshold:
            warnings.append("Image is too blurry. Please capture a clearer image.")
        if brightness < self.s.min_brightness:
            warnings.append("Lighting is too dark. Please capture the pest with better lighting.")
        elif brightness > self.s.max_brightness:
            warnings.append("Lighting is too bright. Please avoid strong overexposure.")
        if contrast < self.s.min_contrast:
            warnings.append("Image contrast is too low. Please capture the pest with clearer visual detail.")
        if edge_density > self.s.max_edge_density:
            warnings.append("Background appears visually complex. Please move closer to the pest and reduce background clutter.")

        return QualityCheck(
            passed=len(warnings) == 0,
            warnings=warnings,
            blur_score=round(blur, 2),
            brightness=round(brightness, 2),
            contrast=round(contrast, 2),
            edge_density=round(edge_density, 4),
            resolution=f"{w}x{h}",
        )
