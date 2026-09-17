from pydantic import BaseModel, Field


class UploadOut(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    key: str = Field(min_length=1, max_length=255)
    content_type: str
    size: int = Field(ge=0)
