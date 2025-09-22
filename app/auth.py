# app/core/auth.py
from __future__ import annotations
from typing import Dict, Any, Optional, Iterable
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
import hashlib
import logging

from app.infrastructure.clients.auth_client import AuthClient


try:
    from app.config import settings
except Exception:
    settings = None  


logger = logging.getLogger("auth")

_auth_client: Optional[AuthClient] = None  # privado no módulo
bearer_scheme = HTTPBearer(auto_error=False)

def _safe_token_id(token: str) -> str:
    # não loga o token; loga um identificador abreviado
    return hashlib.sha1(token.encode()).hexdigest()[:8]

def set_auth_client(client: Optional[AuthClient]) -> None:
    """
    Permite override em testes ou inicialização manual.
    Ex.: set_auth_client(AuthClient(base_url="http://auth-service:8000", ...))
    """
    global _auth_client
    _auth_client = client


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
        try: body = e.response.text[:200]
        except: pass
        sc = getattr(e.response, "status_code", "unknown")
        url = getattr(e.request, "url", "unknown")
        logger.warning("HTTPStatusError em /me (status=%s url=%s body=%r token_id=%s)", sc, url, body, tid)
        if sc in (401, 403):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Falha ao validar token no Auth Service")
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.error("Erro de rede em /me (token_id=%s): %s", tid, e)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth Service inacessível")
async def require_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> Dict[str, Any]:
    """
    Dependency principal. Valida o Bearer e devolve o payload do usuário (ex.: sub, roles, scopes, etc.).
    """
    if credentials is None or (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente")
    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token vazio")

    user = await _fetch_me(token)

    # Se seu /me retorna algo como {"active": true}:
    if isinstance(user, dict) and user.get("active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo")

    return user

def _has_every(scope_needed: Iterable[str], scopes_user: Iterable[str]) -> bool:
    want = set(s.strip() for s in scope_needed if s and s.strip())
    have = set(s.strip() for s in scopes_user if s and s.strip())
    return want.issubset(have)

async def require_scopes(
    scope_list: Iterable[str],
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> Dict[str, Any]:
    """
    Exemplo opcional de dependency para checar escopos além de validar o token.
    Uso: Depends(partial(require_scopes, ["videos:read"]))
    """
    user = await require_user(credentials)
    user_scopes = user.get("scopes") or user.get("scope") or []
    # "scope" pode vir como string "a b c"
    if isinstance(user_scopes, str):
        user_scopes = [s for s in user_scopes.split() if s]

    if not _has_every(scope_list, user_scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Escopo insuficiente")
    return user
