from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime

Role = Literal["admin", "user"]  

class UserContext(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    cpf: Optional[str] = None
    role: Role
    is_active: bool
    created_at: Optional[datetime] = None
