from pathlib import Path
from collections import defaultdict
import json, time
import numpy as np
from PIL import Image
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix, roc_auc_score, f1_score


def load_image_dataset(root: str):
    root = Path(root)
    samples=[]
    class_names=sorted([p.name for p in root.iterdir() if p.is_dir()])
    mapping={name:i for i,name in enumerate(class_names)}
    for name in class_names:
        for p in (root/name).rglob('*'):
            if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}:
                samples.append((p,mapping[name],name))
    return samples, class_names


def evaluate_classifier(classifier, samples):
    y_true=[]; y_pred=[]; confidences=[]; lat=[]
    for path,y,_ in samples:
        image=Image.open(path).convert('RGB')
        t=time.perf_counter(); r=classifier.predict(image); lat.append(time.perf_counter()-t)
        y_true.append(y); y_pred.append(r['index']); confidences.append(r['confidence'])
    acc=accuracy_score(y_true,y_pred)
    precision,recall,f1,_=precision_recall_fscore_support(y_true,y_pred,average='weighted',zero_division=0)
    return {'accuracy':float(acc),'precision':float(precision),'recall':float(recall),'f1':float(f1),'confusion_matrix':confusion_matrix(y_true,y_pred).tolist(),'mean_inference_ms':float(np.mean(lat)*1000),'y_true':y_true,'y_pred':y_pred,'confidence':confidences}


def save_json(data, path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(data,indent=2),encoding='utf-8')
