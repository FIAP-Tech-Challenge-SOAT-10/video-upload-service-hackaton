# models.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Optional

class VideoItem(BaseModel):
    id_video: str
    id_usuario: str
    titulo: str = Field(..., max_length=200)
    autor: str = Field(..., max_length=100)
    status: str
    file_path: str
    data_criacao: datetime = Field(default_factory=datetime.utcnow)
    data_upload: datetime = Field(default_factory=datetime.utcnow)

class UploadResponse(BaseModel):
    id_video: str
    id_usuario: str
    titulo: str = Field(..., max_length=200)
    autor: str = Field(..., max_length=100)
    status: str
    s3_key: str
    links: Optional[Dict[str, str]] = None  # <- acrescentado

class StatusResponse(BaseModel):
    id_video: str
    id_usuario: str
    titulo: str | None = Field(default=None, max_length=200)
    autor: str | None = Field(default=None, max_length=100)
    status: str
    file_path: str | None = None
    data_criacao: datetime | None = None
    data_upload: datetime | None = None
