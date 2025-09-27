# tests/test_auth_client_hooks.py
import logging
import pytest
import httpx

from app.infrastructure.clients.auth_client import AuthClient


@pytest.mark.asyncio
async def test_event_hooks_log_request_and_response(caplog, monkeypatch):
    # Handler para o MockTransport
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "XYZ"}, request=request)
        return httpx.Response(404, json={"detail": "not found"}, request=request)

    # Guarda a classe ORIGINAL antes do patch
    orig_async_client = httpx.AsyncClient

    # Wrapper que injeta o MockTransport, preservando event_hooks
    class AsyncClientWithMock:
        def __init__(self, *, base_url, timeout, event_hooks):
            self._inner = orig_async_client(
                base_url=base_url,
                timeout=timeout,
                event_hooks=event_hooks,
                transport=httpx.MockTransport(handler),
            )

        async def post(self, *a, **kw):
            return await self._inner.post(*a, **kw)

        async def get(self, *a, **kw):
            return await self._inner.get(*a, **kw)

        async def aclose(self):
            await self._inner.aclose()

    # Patcha o AsyncClient usado dentro do módulo do AuthClient
    import app.infrastructure.clients.auth_client as mod
    monkeypatch.setattr(mod.httpx, "AsyncClient", AsyncClientWithMock, raising=True)

    c = AuthClient("http://auth:8000", timeout_seconds=5, cache_ttl=30)

    # Captura logs de DEBUG do logger "auth" (usado nos hooks)
    with caplog.at_level(logging.DEBUG, logger="auth"):
        out = await c.login("iana", "123")
        assert out == {"access_token": "XYZ"}

    # Verifica logs de request e response
    req_msgs = [r.getMessage() for r in caplog.records if "HTTPX request:" in r.getMessage()]
    resp_msgs = [r.getMessage() for r in caplog.records if "HTTPX response:" in r.getMessage()]

    assert any("HTTPX request: POST http://auth:8000/api/v1/auth/login" in m for m in req_msgs)

    # Deve conter método, URL, status e duração calculada (não "?")
    assert any("HTTPX response: POST http://auth:8000/api/v1/auth/login -> 200 (" in m for m in resp_msgs)
    assert not any("-> 200 (?)" in m for m in resp_msgs)

    # Trecho do corpo presente no log
    assert any("access_token" in m for m in resp_msgs)
