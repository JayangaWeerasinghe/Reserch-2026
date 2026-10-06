import logging
import re
from pathlib import Path
import torch
import torch.nn.functional as F
from PIL import Image

logger = logging.getLogger(__name__)

class FewShotStore:
    """Prototype-based few-shot learning on top of a frozen DenseNet121 feature space."""
    def __init__(self, classifier, store_dir: str, similarity_threshold: float = 0.72):
        self.classifier = classifier
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.similarity_threshold = similarity_threshold
        self.prototypes: dict[str, torch.Tensor] = {}
        self._load_all()

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9 _-]", "", name).strip()
        if not cleaned:
            raise ValueError("Pest class name is invalid.")
        return cleaned[:80]

    def _path(self, name: str) -> Path:
        safe = self._safe_name(name).lower().replace(" ", "_")
        return self.store_dir / f"{safe}.pt"

    def _load_all(self):
        for path in self.store_dir.glob("*.pt"):
            try:
                payload = torch.load(path, map_location="cpu", weights_only=True)
                self.prototypes[payload["class_name"]] = payload["prototype"].float()
            except Exception as exc:
                logger.warning("Could not load few-shot prototype %s: %s", path, exc)

    def register(self, class_name: str, images: list[Image.Image]) -> dict:
        class_name = self._safe_name(class_name)
        if len(images) < 5 or len(images) > 20:
            raise ValueError("Please provide between 5 and 20 labelled images for few-shot learning.")

        embeddings = []
        for image in images:
            embeddings.append(self.classifier.extract_embedding(image).squeeze(0).cpu())

        prototype = F.normalize(torch.stack(embeddings).mean(dim=0), dim=0)
        torch.save({"class_name": class_name, "prototype": prototype}, self._path(class_name))
        self.prototypes[class_name] = prototype

        return {
            "class_name": class_name,
            "images_used": len(images),
            "message": f"New pest '{class_name}' learned from {len(images)} labelled images.",
        }

    def classify(self, image: Image.Image):
        if not self.prototypes:
            return None
        embedding = self.classifier.extract_embedding(image).squeeze(0).cpu()
        embedding = F.normalize(embedding, dim=0)
        scores = {
            name: float(torch.dot(embedding, prototype).item())
            for name, prototype in self.prototypes.items()
        }
        name, score = max(scores.items(), key=lambda item: item[1])
        if score >= self.similarity_threshold:
            return {"class_name": name, "similarity": score}
        return None

    def list_classes(self):
        return sorted(self.prototypes.keys())

    def delete(self, class_name: str) -> bool:
        class_name = self._safe_name(class_name)
        path = self._path(class_name)
        removed = class_name in self.prototypes
        self.prototypes.pop(class_name, None)
        if path.exists():
            path.unlink()
            removed = True
        return removed
