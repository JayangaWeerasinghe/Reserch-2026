import logging
from pathlib import Path
import torch
import torch.nn as nn
from torchvision import models, transforms
from pipeline.core.config import Settings

logger = logging.getLogger(__name__)

CLASSES = [
    "Brown Planthopper",
    "Rice Gall Midge",
    "Rice Hispa",
    "Rice Leaf Folder",
    "Rice Stem Borer",
]

class DenseNet121Classifier:
    """Loads the user's trained DenseNet121 checkpoint once and exposes inference helpers."""
    def __init__(self, settings: Settings):
        self.settings = settings
        self.CLASSES = CLASSES
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._build_model(Path(settings.model_path))
        self.transform = transforms.Compose([
            transforms.Resize((settings.image_size, settings.image_size)),
            transforms.ToTensor(),
        ])

    def _build_model(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {path}")

        model = models.densenet121(weights=None)
        # The checkpoint contains classifier.1.*, so the training head was a
        # Sequential(Dropout, Linear) rather than the torchvision default Linear.
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.5),
            nn.Linear(model.classifier.in_features, len(CLASSES)),
        )

        checkpoint = torch.load(path, map_location=self.device, weights_only=True)
        model.load_state_dict(checkpoint, strict=True)
        model.to(self.device)
        model.eval()
        logger.info("Loaded DenseNet121 from %s on %s", path, self.device)
        return model

    def preprocess(self, image):
        return self.transform(image).unsqueeze(0).to(self.device)

    @torch.inference_mode()
    def extract_embedding(self, image):
        tensor = self.preprocess(image)
        features = self.model.features(tensor)
        features = torch.relu(features)
        pooled = torch.nn.functional.adaptive_avg_pool2d(features, (1, 1))
        return torch.flatten(pooled, 1)

    @torch.inference_mode()
    def predict(self, image):
        tensor = self.preprocess(image)
        logits = self.model(tensor)
        probabilities = torch.softmax(logits, dim=1)[0]
        confidence, index = torch.max(probabilities, dim=0)
        return {
            "index": int(index.item()),
            "class_name": CLASSES[int(index.item())],
            "confidence": float(confidence.item()),
            "probabilities": probabilities.detach().cpu().tolist(),
        }
