import json
import pytest
import httpx

from app.infrastructure.clients.auth_client import AuthClient


# ========= Stub/fixture =========

class StubHTTPClient:
    """
    Cliente HTTP assíncrono fake para injetar via monkeypatch em AuthClient._get_client.
    Controla respostas por (method, path) e registra chamadas.
    """
    def __init__(self):
        self.responses = {}  # key: (method, path) -> httpx.Response
        self.calls = []      # lista de dicts com 'method', 'path', 'headers', 'json'
        self.closed = False

    def set_json(self, method: str, path: str, status: int, payload: dict):
        req = httpx.Request(method.upper(), f"http://fake{path}", headers={})
        resp = httpx.Response(
            status_code=status,
            headers={"content-type": "application/json"},
            content=json.dumps(payload).encode("utf-8"),
            request=req,
        )
        self.responses[(method.upper(), path)] = resp

    async def post(self, path: str, json=None, headers=None):
        self.calls.append({"method": "POST", "path": path, "json": json, "headers": headers or {}})
        resp = self.responses.get(("POST", path))
        if resp is None:
            req = httpx.Request("POST", f"http://fake{path}", headers=headers or {})
            return httpx.Response(500, request=req, content=b"")
        return resp

    async def get(self, path: str, headers=None):
        self.calls.append({"method": "GET", "path": path, "json": None, "headers": headers or {}})
        resp = self.responses.get(("GET", path))
        if resp is None:
            req = httpx.Request("GET", f"http://fake{path}", headers=headers or {})
            return httpx.Response(500, request=req, content=b"")
        return resp

    async def aclose(self):
        self.closed = True


@pytest.fixture
def stub_client():
    return StubHTTPClient()


# ========= _get_client (hooks + singleton) =========

@pytest.mark.asyncio
async def test_get_client_builds_asyncclient_with_hooks_and_singleton(monkeypatch):
    captured_init = {}

    class CapturingAsyncClient:
        def __init__(self, *, base_url, timeout, event_hooks):
            captured_init["base_url"] = str(base_url)
            captured_init["timeout"] = timeout
            captured_init["event_hooks"] = event_hooks

    # monkeypatch a classe usada na implementação
    import app.infrastructure.clients.auth_client as mod
    monkeypatch.setattr(mod.httpx, "AsyncClient", CapturingAsyncClient, raising=True)

    client = AuthClient("http://auth:8000", timeout_seconds=7, cache_ttl=30)

    # primeira chamada cria
    ac1 = await client._get_client()
    # segunda chamada retorna o mesmo objeto (singleton)
    ac2 = await client._get_client()
    assert ac1 is ac2

    # confs passadas corretamente
    assert captured_init["base_url"].rstrip("/") == "http://auth:8000"
    assert captured_init["timeout"] == 7
    assert "request" in captured_init["event_hooks"] and "response" in captured_init["event_hooks"]
    assert callable(captured_init["event_hooks"]["request"][0])
    assert callable(captured_init["event_hooks"]["response"][0])


# ========= login =========

@pytest.mark.asyncio
async def test_login_success(monkeypatch, stub_client):
    c = AuthClient("http://auth:8000")

    async def fake_get_client():
        return stub_client
    monkeypatch.setattr(c, "_get_client", fake_get_client, raising=False)

    stub_client.set_json("POST", "/api/v1/auth/login", 200, {"access_token": "XYZ"})

    out = await c.login("iana", "123")
    assert out == {"access_token": "XYZ"}

    # validação de chamada
    assert stub_client.calls == [
        {
            "method": "POST",
            "path": "/api/v1/auth/login",
            "json": {"username": "iana", "password": "123"},
            "headers": {},
        }
    ]


@pytest.mark.asyncio
async def test_login_raises_on_non_2xx(monkeypatch, stub_client):
    c = AuthClient("http://auth:8000")

    async def fake_get_client():
        return stub_client
    monkeypatch.setattr(c, "_get_client", fake_get_client, raising=False)

    # 401
    req = httpx.Request("POST", "http://fake/api/v1/auth/login")
    stub_client.responses[("POST", "/api/v1/auth/login")] = httpx.Response(401, request=req, text="unauthorized")

    with pytest.raises(httpx.HTTPStatusError):
        await c.login("iana", "bad")


# ========= me =========

@pytest.mark.asyncio
async def test_me_success_and_authorization_header_and_cache(monkeypatch, stub_client):
    c = AuthClient("http://auth:8000", cache_ttl=30)

    async def fake_get_client():
        return stub_client
    monkeypatch.setattr(c, "_get_client", fake_get_client, raising=False)

    # controla o relógio (agora=1000, depois=1005 => ainda dentro do TTL)
    times = [1000.0, 1005.0]
    def fake_time():
        return times.pop(0) if times else 1005.0
    monkeypatch.setattr("app.infrastructure.clients.auth_client.time.time", fake_time, raising=True)

    stub_client.set_json("GET", "/api/v1/auth/me", 200, {"id": 1})

    # 1ª chamada: vai à rede
    out1 = await c.me("tok")
    assert out1 == {"id": 1}

    # 2ª chamada: usa cache (não deve fazer novo GET)
    out2 = await c.me("tok")
    assert out2 == {"id": 1}

    # apenas 1 chamada GET registrada
    gets = [call for call in stub_client.calls if call["method"] == "GET"]
    assert len(gets) == 1
    # header Authorization correto
    assert gets[0]["headers"].get("Authorization") == "Bearer tok"


@pytest.mark.asyncio
async def test_me_cache_expires_and_refetches(monkeypatch, stub_client):
    c = AuthClient("http://auth:8000", cache_ttl=30)

    async def fake_get_client():
        return stub_client
    monkeypatch.setattr(c, "_get_client", fake_get_client, raising=False)

    # tempo: 1000 (primeira busca), 1035 (expirou), 1036 (whatever)
    tvals = [1000.0, 1035.0, 1036.0]
    def fake_time():
        return tvals.pop(0)
    monkeypatch.setattr("app.infrastructure.clients.auth_client.time.time", fake_time, raising=True)

    stub_client.set_json("GET", "/api/v1/auth/me", 200, {"id": 1})

    _ = await c.me("tok")  # primeira (cachea até 1030)
    _ = await c.me("tok")  # expirada => refaz GET

    gets = [call for call in stub_client.calls if call["method"] == "GET"]
    assert len(gets) == 2  # refetch


@pytest.mark.asyncio
async def test_me_raises_on_non_2xx(monkeypatch, stub_client):
    c = AuthClient("http://auth:8000")

    async def fake_get_client():
        return stub_client
    monkeypatch.setattr(c, "_get_client", fake_get_client, raising=False)

    req = httpx.Request("GET", "http://fake/api/v1/auth/me")
    stub_client.responses[("GET", "/api/v1/auth/me")] = httpx.Response(500, request=req, text="boom")

    with pytest.raises(httpx.HTTPStatusError):
        await c.me("tok")


@pytest.mark.asyncio
async def test_me_cache_is_per_token(monkeypatch, stub_client):
    c = AuthClient("http://auth:8000", cache_ttl=30)

    async def fake_get_client():
        return stub_client
    monkeypatch.setattr(c, "_get_client", fake_get_client, raising=False)

    # tempo constante dentro do TTL
    monkeypatch.setattr("app.infrastructure.clients.auth_client.time.time", lambda: 1000.0, raising=True)

    # mesma resposta para simplificar
    stub_client.set_json("GET", "/api/v1/auth/me", 200, {"id": 1})

    await c.me("tok-A")  # cache para tok-A
    await c.me("tok-B")  # deve ir à rede (token diferente)
    gets = [call for call in stub_client.calls if call["method"] == "GET"]
    assert len(gets) == 2


# ========= aclose =========

@pytest.mark.asyncio
async def test_aclose_closes_and_resets():
    c = AuthClient("http://auth:8000")

    stub = StubHTTPClient()
    # força o cliente interno
    c._client = stub

    await c.aclose()
    assert stub.closed is True
    assert c._client is None
