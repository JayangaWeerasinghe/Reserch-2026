"""Fit Mahalanobis OOD reference statistics from a labelled dataset.
Usage: python scripts/build_ood_reference.py --dataset data/train --threshold 15
Dataset format: dataset/ClassName/*.jpg
"""
import argparse
from pathlib import Path
import torch
from PIL import Image
from pipeline.core.config import get_settings
from pipeline.ml.model_loader import DenseNet121Classifier
from pipeline.ml.ood import MahalanobisOOD

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dataset',required=True); ap.add_argument('--threshold',type=float,default=None); args=ap.parse_args()
    s=get_settings(); clf=DenseNet121Classifier(s)
    paths=[]; labels=[]; classes=sorted([p for p in Path(args.dataset).iterdir() if p.is_dir()])
    for i,c in enumerate(classes):
        for p in c.rglob('*'):
            if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}: paths.append(p); labels.append(i)
    emb=[]
    for p in paths:
        emb.append(clf.extract_embedding(Image.open(p).convert('RGB')).squeeze(0).cpu())
    detector=MahalanobisOOD(s.ood_reference_path,s.ood_mahalanobis_threshold)
    detector.fit(torch.stack(emb),torch.tensor(labels),args.threshold)
    print(f'Fitted OOD reference using {len(paths)} images across {len(classes)} classes.')
    print(f'Saved: {s.ood_reference_path}')
if __name__=='__main__': main()
