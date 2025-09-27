import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import httpx
from types import SimpleNamespace

import app.core.auth as auth_mod


# ====== Fixtures utilitárias ======

@pytest.fixture(autouse=True)
def reset_auth_globals(monkeypatch):
    # Garante estado limpo entre testes
    monkeypatch.setattr(auth_mod, "auth_client", None, raising=False)
    # _auth_client pode não existir; ainda assim setamos/limpamos
    if not hasattr(auth_mod, "_auth_client"):
        monkeypatch.setattr(auth_mod, "_auth_client", None, raising=False)
    else:
        auth_mod._auth_client = None
    # Garante que except httpx.* funcione (caso httpx não tenha sido importado no módulo)
    monkeypatch.setattr(auth_mod, "httpx", httpx, raising=False)
    yield
    auth_mod.auth_client = None
    auth_mod._auth_client = None


# ====== _safe_token_id ======

def test_safe_token_id_is_deterministic_and_short():
    t1 = auth_mod._safe_token_id("abc")
    t2 = auth_mod._safe_token_id("abc")
    t3 = auth_mod._safe_token_id("xyz")
    assert t1 == t2
    assert t1 != t3
    assert len(t1) == 8  # sha1 abreviado


# ====== _ensure_client ======

def test_ensure_client_initializes_on_demand(monkeypatch):
    # Patching do settings consumido dentro da função
    import app.config as cfg
    monkeypatch.setattr(
        cfg,
        "settings",
        SimpleNamespace(
            auth_base_url="http://auth:8000",
            auth_timeout_seconds=5,
            auth_cache_ttl_seconds=60,
        ),
        raising=False,
    )

    # Patch do AuthClient usado pelo import interno
    import app.infrastructure.clients.auth_client as acmod

    created = {}
    class FakeAuthClient:
        def __init__(self, base_url, timeout_seconds, cache_ttl):
            created["base_url"] = base_url
            created["timeout_seconds"] = timeout_seconds
            created["cache_ttl"] = cache_ttl

        async def me(self, token):  # só p/ compatibilidade
            return {"ok": True}

    monkeypatch.setattr(acmod, "AuthClient", FakeAuthClient, raising=True)

    c1 = auth_mod._ensure_client()
    c2 = auth_mod._ensure_client()
    assert isinstance(c1, FakeAuthClient)
    assert c2 is c1  # cache global
    assert created == {
        "base_url": "http://auth:8000",
        "timeout_seconds": 5,
        "cache_ttl": 60,
    }


def test_ensure_client_missing_base_url_returns_503(monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(
        cfg,
        "settings",
        SimpleNamespace(
            auth_base_url="",
            auth_timeout_seconds=5,
            auth_cache_ttl_seconds=60,
        ),
        raising=False,
    )
    with pytest.raises(HTTPException) as ex:
        auth_mod._ensure_client()
    assert ex.value.status_code == 503
    assert "indisponível" in ex.value.detail.lower()


def test_ensure_client_settings_failure_returns_503(monkeypatch):
    import app.config as cfg

    class Boom:
        def __getattr__(self, name):
            raise RuntimeError("boom")

    monkeypatch.setattr(cfg, "settings", Boom(), raising=False)
    with pytest.raises(HTTPException) as ex:
        auth_mod._ensure_client()
    assert ex.value.status_code == 503


# ====== _fetch_me (mapeamento de erros do httpx) ======

@pytest.mark.asyncio
async def test_fetch_me_ok(monkeypatch):
    class FakeClient:
        async def me(self, token):
            return {"email": "user@example.com"}

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeClient())
    out = await auth_mod._fetch_me("token-123")
    assert out["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_fetch_me_httpstatus_401_to_401(monkeypatch):
    req = httpx.Request("GET", "http://auth/me")
    resp = httpx.Response(401, text="bad token", request=req)

    class FakeClient:
        async def me(self, token):
            raise httpx.HTTPStatusError("err", request=req, response=resp)

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeClient())
    with pytest.raises(HTTPException) as ex:
        await auth_mod._fetch_me("bad-token")
    assert ex.value.status_code == 401
    assert "inválido" in ex.value.detail.lower() or "expirado" in ex.value.detail.lower()


@pytest.mark.asyncio
async def test_fetch_me_httpstatus_500_to_503(monkeypatch):
    req = httpx.Request("GET", "http://auth/me")
    resp = httpx.Response(500, text="oops", request=req)

    class FakeClient:
        async def me(self, token):
            raise httpx.HTTPStatusError("err", request=req, response=resp)

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeClient())
    with pytest.raises(HTTPException) as ex:
        await auth_mod._fetch_me("token")
    assert ex.value.status_code == 503


@pytest.mark.asyncio
async def test_fetch_me_timeout_to_503(monkeypatch):
    class FakeClient:
        async def me(self, token):
            raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeClient())
    with pytest.raises(HTTPException) as ex:
        await auth_mod._fetch_me("token")
    assert ex.value.status_code == 503


# ====== get_auth_client ======

def test_get_auth_client_asserts_when_none(monkeypatch):
    monkeypatch.setattr(auth_mod, "auth_client", None, raising=False)
    with pytest.raises(AssertionError):
        auth_mod.get_auth_client()


def test_get_auth_client_returns_instance(monkeypatch):
    class FakeClient: ...
    monkeypatch.setattr(auth_mod, "auth_client", FakeClient(), raising=False)
    c = auth_mod.get_auth_client()
    assert isinstance(c, FakeClient)


# ====== get_current_user (dependência FastAPI) ======

@pytest.mark.asyncio
async def test_get_current_user_ok(monkeypatch):
    class FakeClient:
        async def me(self, token): return {"id": 1}

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="abc")
    user = await auth_mod.get_current_user(
        credentials=creds,
        client=FakeClient(),
    )
    assert user == {"id": 1}


@pytest.mark.asyncio
async def test_get_current_user_missing_header_401():
    with pytest.raises(HTTPException) as ex:
        await auth_mod.get_current_user(credentials=None, client=None)
    assert ex.value.status_code == 401
    assert "missing" in ex.value.detail.lower()


@pytest.mark.asyncio
async def test_get_current_user_invalid_token_401(monkeypatch):
    class FakeClient:
        async def me(self, token): raise RuntimeError("nope")

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad")
    with pytest.raises(HTTPException) as ex:
        await auth_mod.get_current_user(credentials=creds, client=FakeClient())
    assert ex.value.status_code == 401
    assert "invalid token" in ex.value.detail.lower()
