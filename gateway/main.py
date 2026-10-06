"""
PaddyGuard AI — API Gateway
Receives all client requests and routes them to the correct microservice.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

from router import voice, image, pest, chat, user

app = FastAPI(
    title="PaddyGuard AI — API Gateway",
    description="Central gateway for all PaddyGuard AI microservices",
    version="1.0.0"
)

# CORS — allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if origin.strip()],
    allow_credentials="*" not in [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# Include service routers
app.include_router(voice.router, prefix="/api/v1/voice", tags=["Voice NLP — C1"])
app.include_router(image.router, prefix="/api/v1/image", tags=["Leaf Disease — C2"])
app.include_router(pest.router,  prefix="/api/v1/pest",  tags=["Pest Detection — C3"])
app.include_router(chat.router,  prefix="/api/v1/chat",  tags=["Treatment Chatbot — C4"])
app.include_router(user.router,  prefix="/api/v1/auth",  tags=["User Management"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "gateway", "version": "1.0.0"}

@app.get("/")
def root():
    return {"message": "PaddyGuard AI Gateway is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0",
                port=int(os.getenv("PORT", os.getenv("GATEWAY_PORT", "8000"))), reload=False)
