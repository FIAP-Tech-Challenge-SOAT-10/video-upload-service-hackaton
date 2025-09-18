# app/core/auth.py
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.infrastructure.clients.auth_client import AuthClient

auth_client: Optional[AuthClient] = None  # inicializado no lifespan (main.py)
security_scheme = HTTPBearer(auto_error=False)

def get_auth_client() -> AuthClient:
    assert auth_client is not None, "AuthClient não inicializado"
    return auth_client

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    client: AuthClient = Depends(get_auth_client),
) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    token = credentials.credentials
    try:
        user = await client.me(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return user
