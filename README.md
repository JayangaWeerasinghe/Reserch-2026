# PaddyGuard AI
Multimodal Intelligent System for Rice Disease and Pest Management
Research Project ID: R26-SE-015 | SLIIT

## Services
| Service | Port | Tech | Owner |
|---|---|---|---|
| frontend | 5173 | React + Vite + TypeScript | All |
| gateway | 8000 | FastAPI | All |
| voice_nlp | 8001 | FastAPI + SVM + Whisper | Jayonga IT22273680 |
| leaf_disease_detection | 8002 | FastAPI + PyTorch CNN | Lasiru IT22168740 |
| pest_detection | 8003 | FastAPI + YOLOv8 | Kalhara IT22065858 |
| treatment_advisory_chatbot | 8004 | Node.js + Express + RAG | Keshan IT22303820 |
| user_management | 8005 | FastAPI + PostgreSQL | All |

## Prerequisites
- Docker Desktop installed and running
- Git
- Models in place:
  - `voice_nlp/models/paddyguard_best_classifier.pkl`
  - `voice_nlp/models/paddyguard_tfidf.pkl`
  - `leaf_disease_detection/models/` (as required by C2)
  - `pest_detection/models/` (as required by C3)

## Environment Files
Copy and fill in each service's env file:
```bash
cp gateway/.env.example gateway/.env
cp voice_nlp/.env.example voice_nlp/.env
cp leaf_disease_detection/.env.example leaf_disease_detection/.env
cp pest_detection/.env.example pest_detection/.env
cp user_management/.env.example user_management/.env
cp frontend/.env.example frontend/.env
```

## Start Order (Development)

### Option A — Full Docker (recommended for demo)
```bash
docker compose up --build
```
Then open: http://localhost

### Option B — Mixed (backend in Docker, frontend on Vite for hot reload)
```bash
# Terminal 1 — start all backend services
docker compose up postgres mongo user_management gateway \
  voice_nlp leaf_disease_detection pest_detection \
  treatment_advisory_chatbot --build -d

# Terminal 2 — start frontend with hot reload
cd frontend
npm install
npm run dev
```
Then open: http://localhost:5173

## Service URLs
| Service | URL |
|---|---|
| Frontend | http://localhost:5173 (dev) or http://localhost (prod) |
| Gateway | http://localhost:8000 |
| voice_nlp | http://localhost:8001 |
| leaf_disease_detection | http://localhost:8002 |
| pest_detection | http://localhost:8003 |
| treatment_advisory_chatbot | http://localhost:8004 |
| user_management | http://localhost:8005 |
| PostgreSQL | localhost:5432 |
| MongoDB | localhost:27017 |

## Default Credentials
- Register a farmer account at http://localhost:5173/register (this also transparently creates a matching account on the leaf disease service so `/leaf` history works).
- Staff (expert / super admin) login is at http://localhost:5173/staff-login. Staff accounts are created via `leaf_disease_detection`'s super admin credentials (`SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD` in its `.env`) and, from there, the Expert Management page.

## Deployment
- Frontend: Vercel (auto-deploy on push to main)
- All backend services: GCP Cloud Run / AWS ECS / Azure Container Apps
