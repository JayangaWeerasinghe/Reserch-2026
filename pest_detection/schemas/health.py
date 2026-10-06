from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    device: str
    model_name: str
