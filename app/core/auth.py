# app/core/auth.py
from typing import Any, Dict, Optional
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.infrastructure.clients.auth_client import AuthClient

import hashlib
import logging


auth_client: Optional[AuthClient] = None  # inicializado no lifespan (main.py)
security_scheme = HTTPBearer(auto_error=False)

logger = logging.getLogger("auth")

def _safe_token_id(token: str) -> str:
    return hashlib.sha1(token.encode()).hexdigest()[:8]

def _ensure_client():
    global _auth_client
    if _auth_client is not None:
        return _auth_client
    # cria on-demand a partir de settings
    try:
        from app.config import settings
        base_url = settings.auth_base_url
        timeout = settings.auth_timeout_seconds
        ttl = settings.auth_cache_ttl_seconds
    except Exception as e:
        logger.error("Falha ao carregar settings p/ AuthClient: %s", e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Serviço de autenticação indisponível")

    if not base_url:
        logger.error("AUTH_BASE_URL ausente; não dá para inicializar AuthClient")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Serviço de autenticação indisponível")

    from app.infrastructure.clients.auth_client import AuthClient
    _auth_client = AuthClient(base_url=base_url, timeout_seconds=timeout, cache_ttl=ttl)
    logger.info("AuthClient criado on-demand (base_url=%s)", base_url)
    return _auth_client

async def _fetch_me(token: str):
    tid = _safe_token_id(token)
    client = _ensure_client()

    try:
        logger.debug("Chamando /me (token_id=%s)", tid)
        data = await client.me(token)
        logger.info("Auth OK (token_id=%s)", tid)
        return data
    except httpx.HTTPStatusError as e:
        body = ""
        body = e.response.text[:200]
        sc = getattr(e.response, "status_code", "unknown")
        url = getattr(e.request, "url", "unknown")
        logger.warning("HTTPStatusError em /me (status=%s url=%s body=%r token_id=%s)", sc, url, body, tid)
        if sc in (401, 403):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Falha ao validar token no Auth Service")
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.error("Erro de rede em /me (token_id=%s): %s", tid, e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth Service inacessível")
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
