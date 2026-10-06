from PIL import Image
import numpy as np

from pipeline.core.config import Settings
from pipeline.services.image_quality import ImageQualityService


def test_quality_service_accepts_clear_image():
    arr = np.random.default_rng(7).integers(
        0, 255, (512, 512, 3), dtype=np.uint8
    )
    image = Image.fromarray(arr)
    result = ImageQualityService(Settings()).evaluate(image)
    assert result.resolution == "512x512"
    assert result.blur_score >= 0
