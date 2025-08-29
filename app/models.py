from pydantic import BaseModel, Field
from datetime import datetime

class VideoItem(BaseModel):
    id: str
    user_id: str
    title: str = Field(..., max_length=200)
    status: str
    file_path: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UploadResponse(BaseModel):
    id: str
    title: str = Field(..., max_length=200)
    status: str
    s3_key: str

class StatusResponse(BaseModel):
    id: str
    title: str | None = Field(default=None, max_length=200)
    status: str
    file_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
