import base64
from io import BytesIO
from pathlib import Path
from typing import Dict

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms

from .config import settings

CLASS_NAMES = ["Bacterial_Blight", "Brown_Spot", "Healthy", "Leaf_Blast"]
IMAGE_SIZE = 300
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class ModelService:
    def __init__(self):
        self.model = None
        self.gradients = None
        self.activations = None
        self.transform = transforms.Compose([
            transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self._load()

    def reload(self):
        print("Reloading model from", settings.model_path)
        self._load()

    def _load(self):
        path = Path(settings.model_path)
        if not path.exists():
            print(f"WARNING: model not found at {path}. API health works, prediction will fail.")
            return

        model = models.efficientnet_b3(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.4),
            nn.Linear(in_features, len(CLASS_NAMES)),
        )
        checkpoint = torch.load(path, map_location=DEVICE, weights_only=False)
        
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        else:
            state_dict = checkpoint
            
        model.load_state_dict(state_dict)
        model.to(DEVICE).eval()

        target_layer = model.features[-1]
        target_layer.register_forward_hook(self._forward_hook)
        target_layer.register_full_backward_hook(self._backward_hook)
        self.model = model

    def _forward_hook(self, module, inputs, output):
        self.activations = output

    def _backward_hook(self, module, grad_input, grad_output):
        self.gradients = grad_output[0]

    def _gradcam(self, tensor, class_idx: int):
        self.model.zero_grad(set_to_none=True)
        output = self.model(tensor)
        output[:, class_idx].sum().backward()

        gradients = self.gradients.detach()[0]
        activations = self.activations.detach()[0]
        weights = gradients.mean(dim=(1, 2))
        cam = (weights[:, None, None] * activations).sum(dim=0)
        cam = torch.relu(cam)
        cam = cam.cpu().numpy()
        cam = cv2.resize(cam, (IMAGE_SIZE, IMAGE_SIZE))
        max_value = float(cam.max())
        return cam / max_value if max_value > 0 else np.zeros_like(cam)

    def _overlay_base64(self, image: Image.Image, cam: np.ndarray):
        original = np.array(image.resize((IMAGE_SIZE, IMAGE_SIZE)).convert("RGB"))
        heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        overlay = np.clip(original * 0.6 + heatmap * 0.4, 0, 255).astype(np.uint8)
        output = BytesIO()
        Image.fromarray(overlay).save(output, format="PNG")
        return base64.b64encode(output.getvalue()).decode("utf-8")

    def predict(self, image: Image.Image) -> Dict:
        if self.model is None:
            raise RuntimeError(
                "Model file not found. Copy best_efficientnetb3_initial.pth into backend/models/"
            )

        image = image.convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(DEVICE)

        with torch.no_grad():
            logits = self.model(tensor)
            probabilities = F.softmax(logits, dim=1)
            confidence, predicted = probabilities.max(dim=1)
            energy = torch.logsumexp(logits, dim=1)

        confidence_value = float(confidence.item())
        class_idx = int(predicted.item())
        energy_value = float(energy.item())

        class_probabilities = {CLASS_NAMES[i]: float(probabilities[0][i].item()) for i in range(len(CLASS_NAMES))}

        is_low_confidence = (confidence_value < settings.low_confidence_threshold)

        if energy_value < settings.ood_energy_threshold:
            return {
                "status": "OOD",
                "prediction": "Unknown image (not a recognised rice leaf)",
                "confidence": round(confidence_value, 4),
                "energy_score": round(energy_value, 4),
                "is_low_confidence": False,
                "needs_expert_review": False,
                "severity_percentage": None,
                "severity_method": None,
                "gradcam_base64": None,
                "class_probabilities": class_probabilities,
            }

        if confidence_value < settings.uncertain_threshold:
            return {
                "status": "UNCERTAIN",
                "prediction": CLASS_NAMES[class_idx],
                "confidence": round(confidence_value, 4),
                "energy_score": round(energy_value, 4),
                "is_low_confidence": is_low_confidence,
                "needs_expert_review": is_low_confidence,
                "severity_percentage": None,
                "severity_method": None,
                "gradcam_base64": None,
                "class_probabilities": class_probabilities,
            }

        cam = self._gradcam(tensor, class_idx)
        # Temporary attention proxy. Replace with segmentation model.
        activation_threshold = 0.55
        active_pixels = (cam >= activation_threshold)
        active_pixel_count = int(active_pixels.sum())
        total_pixel_count = int(cam.size)
        severity = (active_pixel_count / total_pixel_count) * 100

        return {
            "status": "KNOWN",
            "prediction": CLASS_NAMES[class_idx],
            "confidence": round(confidence_value, 4),
            "energy_score": round(energy_value, 4),
            "is_low_confidence": is_low_confidence,
            "needs_expert_review": is_low_confidence,
            "severity_percentage": round(severity, 2),
            "severity_method": "gradcam_attention_proxy",
            "gradcam_base64": self._overlay_base64(image, cam),
            "class_probabilities": class_probabilities,
            "severity_breakdown": {
                "activation_threshold": activation_threshold,
                "active_pixel_count": active_pixel_count,
                "total_pixel_count": total_pixel_count,
            }
        }

model_service = ModelService()
