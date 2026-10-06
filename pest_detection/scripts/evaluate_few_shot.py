"""Run 5/10/20-shot prototype experiments.
Dataset format: data/few_shot_experiment/<class>/*.jpg
The script reports prototype similarity classification accuracy for each k.
"""
import argparse, json
from pathlib import Path
import torch
from PIL import Image
from pipeline.core.config import get_settings
from pipeline.ml.model_loader import DenseNet121Classifier
from pipeline.ml.few_shot import FewShotStore

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dataset',required=True); ap.add_argument('--shots',default='5,10,20'); a=ap.parse_args()
    s=get_settings(); clf=DenseNet121Classifier(s); root=Path(a.dataset); classes=sorted([p for p in root.iterdir() if p.is_dir()]); result={}
    for k in [int(x) for x in a.shots.split(',')]:
        protos={}
        for c in classes:
            imgs=[Image.open(p).convert('RGB') for p in sorted(c.rglob('*')) if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}][:k]
            if len(imgs)<k: continue
            embs=[clf.extract_embedding(im).squeeze(0).cpu() for im in imgs]
            protos[c.name]=torch.nn.functional.normalize(torch.stack(embs).mean(0),dim=0)
        correct=total=0
        for c in classes:
            for p in sorted(c.rglob('*'))[k:]:
                if p.suffix.lower() not in {'.jpg','.jpeg','.png','.webp'}: continue
                e=torch.nn.functional.normalize(clf.extract_embedding(Image.open(p).convert('RGB')).squeeze(0).cpu(),dim=0)
                pred=max(protos,key=lambda n:float(torch.dot(e,protos[n])))
                correct += pred==c.name; total += 1
        result[str(k)]={'correct':correct,'total':total,'accuracy':correct/total if total else None}
    out=Path('data/evaluation/few_shot.json'); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
if __name__=='__main__': main()
