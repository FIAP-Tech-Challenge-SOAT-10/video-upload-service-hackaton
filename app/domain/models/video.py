from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Optional

class VideoItem(BaseModel):
    id_video: str
    titulo: str = Field(..., max_length=200)
    autor: str = Field(..., max_length=100)
    status: str
    file_path: str
    data_criacao: datetime = Field(default_factory=datetime.utcnow)
    data_upload: datetime = Field(default_factory=datetime.utcnow)
    email: Optional[str] = None
    username: Optional[str] = None
    id: Optional[str] = None