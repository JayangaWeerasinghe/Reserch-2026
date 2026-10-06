from pydantic import BaseModel, Field

class FewShotRegisterResponse(BaseModel):
    class_name: str
    images_used: int = Field(ge=5, le=20)
    message: str

class FewShotClassesResponse(BaseModel):
    classes: list[str]
