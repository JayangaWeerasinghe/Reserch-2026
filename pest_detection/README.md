# PaddyGuard AI — C3 Rice Pest Detection

Research-facing structure for the PaddyGuard AI rice pest detection component.

## Core model
- DenseNet121
- Five base pest classes
- Image quality awareness
- Mahalanobis OOD / Unknown Pest detection
- Grad-CAM explainability
- Prototype few-shot learning
- Selective fine-tuning for a new pest using 5–20 labelled images

## Research structure
```text
pest_detection/
├── api/
│   └── endpoints.py
├── pipeline/
│   ├── detector.py
│   ├── core/
│   ├── ml/
│   ├── services/
│   └── research/
├── schemas/
│   └── request_schema.py
├── models/
│   └── best_model.pth
├── data/
├── scripts/
├── tests/
├── main.py
├── requirements.txt
├── .env.example
└── Dockerfile
```

The internal `pipeline/ml` and `pipeline/services` modules are the original
working implementation moved under the research structure. The frontend API
contract remains compatible with `/api/v1/predict`, `/api/v1/few-shot/*`, and
`/api/v1/health`. A research-compatible `/detect` route is also exposed.

## Run

```powershell
cd pest_detection
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs

## Important
Do not commit `.env`, `.venv`, or temporary runtime files. The trained
DenseNet121 checkpoint is included because it is required to run the service.
