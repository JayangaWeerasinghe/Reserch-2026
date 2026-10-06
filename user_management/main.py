"""
PaddyGuard AI — User Management Service
Handles: registration, login, JWT issuing/refresh, and profile management.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from models.user import init_db
from routes import auth, profile

app = FastAPI(
    title="PaddyGuard AI — User Management",
    description="Registration, authentication, and profile management",
    version="1.0.0"
)
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if origin.strip()],
                   allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router)
app.include_router(profile.router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "user_management"}

@app.get("/")
def root():
    return {"message": "PaddyGuard AI User Management service is running"}

@app.on_event("startup")
async def startup():
    print("[user_management] service starting on port", os.getenv("PORT", os.getenv("SERVICE_PORT", "8005")))
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0",
                port=int(os.getenv("PORT", os.getenv("SERVICE_PORT", "8005"))), reload=False)
