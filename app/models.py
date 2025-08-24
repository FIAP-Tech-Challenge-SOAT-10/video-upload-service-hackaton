from pydantic import BaseModel, Field
from datetime import datetime

class VideoItem(BaseModel):
    id: str
    user_id: str
    status: str
    file_path: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class UploadResponse(BaseModel):
    id: str
    status: str
    s3_key: str

class StatusResponse(BaseModel):
    id: str
    status: str
    file_path: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
