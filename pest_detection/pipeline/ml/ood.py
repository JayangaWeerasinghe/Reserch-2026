import json
from pathlib import Path
import numpy as np
import torch

class MahalanobisOOD:
    """Optional Mahalanobis OOD detector fitted from training embeddings."""
    def __init__(self, reference_path: str, threshold: float = 15.0):
        self.reference_path = Path(reference_path)
        self.threshold = threshold
        self.means = None
        self.inv_cov = None
        self._load()

    @property
    def ready(self):
        return self.means is not None and self.inv_cov is not None

    def _load(self):
        if not self.reference_path.exists():
            return
        payload = torch.load(self.reference_path, map_location='cpu', weights_only=True)
        self.means = payload['means'].float()
        self.inv_cov = payload['inv_cov'].float()
        self.threshold = float(payload.get('threshold', self.threshold))

    def fit(self, embeddings: torch.Tensor, labels: torch.Tensor, threshold: float | None = None):
        embeddings = embeddings.float().cpu()
        labels = labels.long().cpu()
        classes = sorted(labels.unique().tolist())
        means = []
        centered = []
        for c in classes:
            x = embeddings[labels == c]
            mu = x.mean(dim=0)
            means.append(mu)
            centered.append(x - mu)
        z = torch.cat(centered, dim=0)
        cov = torch.cov(z.T) if z.shape[0] > 1 else torch.eye(z.shape[1])
        cov = cov + torch.eye(cov.shape[0]) * 1e-3
        self.means = torch.stack(means)
        self.inv_cov = torch.linalg.pinv(cov)
        if threshold is not None:
            self.threshold = threshold
        self.reference_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({'means': self.means, 'inv_cov': self.inv_cov, 'threshold': self.threshold}, self.reference_path)
        return self

    def score(self, embedding: torch.Tensor) -> float:
        if not self.ready:
            return float('nan')
        x = embedding.float().cpu().reshape(1, -1)
        d = x[:, None, :] - self.means[None, :, :]
        md2 = torch.einsum('ncd,de,nce->nc', d, self.inv_cov, d).squeeze(0)
        return float(md2.min().item())

    def is_unknown(self, embedding: torch.Tensor):
        if not self.ready:
            return None
        score = self.score(embedding)
        return score > self.threshold, score
