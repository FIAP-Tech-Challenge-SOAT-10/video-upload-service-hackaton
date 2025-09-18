# app/infrastructure/clients/auth_client.py
from __future__ import annotations
import time
from typing import Any, Dict, Optional

import httpx


class AuthClient:
    """Client fino para conversar com o Auth Service."""
    def __init__(self, base_url: str, timeout_seconds: int = 5, cache_ttl: int = 30):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._cache_ttl = cache_ttl
        self._client: Optional[httpx.AsyncClient] = None
        # cache em memória para /me (token -> payload,exp)
        self._cache: Dict[str, tuple[float, Dict[str, Any]]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout)
        return self._client

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        client = await self._get_client()
        resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
        resp.raise_for_status()
        return resp.json()

    async def me(self, token: str) -> Dict[str, Any]:
        now = time.time()
        cached = self._cache.get(token)
        if cached and cached[0] > now:
            return cached[1]

        client = await self._get_client()
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        resp.raise_for_status()
        data = resp.json()
        # guarda no cache por TTL
        self._cache[token] = (now + self._cache_ttl, data)
        return data

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
