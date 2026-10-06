"""Evaluate DenseNet121 on a labelled test set and save research metrics.
Usage: python scripts/evaluate_model.py --dataset data/test --output data/evaluation/classification.json
"""
import argparse
from pipeline.core.config import get_settings
from pipeline.ml.model_loader import DenseNet121Classifier
from pipeline.research.evaluation import load_image_dataset,evaluate_classifier,save_json

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--dataset',required=True); ap.add_argument('--output',default='data/evaluation/classification.json'); a=ap.parse_args()
    s=get_settings(); clf=DenseNet121Classifier(s); samples,classes=load_image_dataset(a.dataset)
    r=evaluate_classifier(clf,samples); r['classes']=classes; save_json(r,a.output)
    print('Accuracy:',round(r['accuracy']*100,2),'%'); print('Precision:',round(r['precision'],4)); print('Recall:',round(r['recall'],4)); print('F1:',round(r['f1'],4)); print('Saved:',a.output)
if __name__=='__main__': main()
