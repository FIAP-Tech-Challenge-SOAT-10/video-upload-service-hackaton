import hashlib
import importlib
import pytest
import httpx
from fastapi.security import HTTPAuthorizationCredentials

# --- escolha o módulo certo: preferimos app.auth; se não existir/faltar a função, caímos para app.core.auth
try:
    auth_mod = importlib.import_module("app.auth")
    if not hasattr(auth_mod, "require_user"):
        raise AttributeError("require_user ausente em app.auth")
except Exception:
    auth_mod = importlib.import_module("app.core.auth")

# ---------- helpers ----------

def cred(token="test-token"):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

class DummyUserContext:
    """Substitui UserContext real para não depender do modelo."""
    def __init__(self, **payload):
        self._data = dict(payload)

    def get(self, k, default=None):
        return self._data.get(k, default)

    @property
    def data(self):
        return dict(self._data)

@pytest.fixture(autouse=True)
def reset_auth_client():
    # Garante estado limpo do singleton entre testes
    if hasattr(auth_mod, "_auth_client"):
        auth_mod._auth_client = None
    yield
    if hasattr(auth_mod, "_auth_client"):
        auth_mod._auth_client = None

# ---------- require_user ----------

@pytest.mark.asyncio
async def test_require_user_success(monkeypatch):
    class FakeAuthClientOK:
        async def me(self, token: str):
            return {
                "username": "tester",
                "email": "user@example.com",
                "id": 123,
                "role": "admin",
                "is_active": True,
            }

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeAuthClientOK(), raising=True)
    monkeypatch.setattr(auth_mod, "UserContext", DummyUserContext, raising=True)

    user = await auth_mod.require_user(cred("abc"))
    assert isinstance(user, DummyUserContext)
    assert user.data["username"] == "tester"
    assert user.data["email"] == "user@example.com"

@pytest.mark.asyncio
async def test_require_user_missing_credentials():
    with pytest.raises(auth_mod.HTTPException) as ex:
        await auth_mod.require_user(None)
    assert ex.value.status_code == 401
    assert "Missing bearer token" in ex.value.detail

@pytest.mark.asyncio
async def test_require_user_invalid_payload_gera_502(monkeypatch):
    class FakeAuthClientOK:
        async def me(self, token: str):
            return {"foo": "bar"}  # payload que não cabe no modelo

    class ExplosiveUserContext:
        def __init__(self, **payload):
            raise ValueError("bad payload")

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeAuthClientOK(), raising=True)
    monkeypatch.setattr(auth_mod, "UserContext", ExplosiveUserContext, raising=True)

    with pytest.raises(auth_mod.HTTPException) as ex:
        await auth_mod.require_user(cred())
    assert ex.value.status_code == 502
    assert "Invalid /me payload" in ex.value.detail

# ---------- _fetch_me (mapeamento de erros) ----------

@pytest.mark.asyncio
async def test_fetch_me_mapeia_401(monkeypatch):
    req = httpx.Request("GET", "http://auth/me")
    resp = httpx.Response(401, request=req, text="unauthorized")
    err = httpx.HTTPStatusError("unauth", request=req, response=resp)

    class FakeAuthClientBoom:
        async def me(self, token: str):
            raise err

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeAuthClientBoom(), raising=True)

    with pytest.raises(auth_mod.HTTPException) as ex:
        await auth_mod._fetch_me("tok")
    assert ex.value.status_code == 401

@pytest.mark.asyncio
async def test_fetch_me_mapeia_500_para_503(monkeypatch):
    req = httpx.Request("GET", "http://auth/me")
    resp = httpx.Response(500, request=req, text="boom")
    err = httpx.HTTPStatusError("server error", request=req, response=resp)

    class FakeAuthClientBoom:
        async def me(self, token: str):
            raise err

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeAuthClientBoom(), raising=True)

    with pytest.raises(auth_mod.HTTPException) as ex:
        await auth_mod._fetch_me("tok")
    assert ex.value.status_code == 503
    assert "Falha ao validar token" in ex.value.detail

@pytest.mark.asyncio
async def test_fetch_me_timeout_vira_503(monkeypatch):
    class FakeAuthClientTimeout:
        async def me(self, token: str):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(auth_mod, "_ensure_client", lambda: FakeAuthClientTimeout(), raising=True)

    with pytest.raises(auth_mod.HTTPException) as ex:
        await auth_mod._fetch_me("tok")
    assert ex.value.status_code == 503
    assert "inacess" in ex.value.detail.lower()  # "inacessível"

# ---------- require_scopes ----------

@pytest.mark.asyncio
async def test_require_scopes_sucesso_lista(monkeypatch):
    async def fake_require_user(_cred):
        return {"scopes": ["videos:read", "videos:write"]}

    monkeypatch.setattr(auth_mod, "require_user", fake_require_user, raising=True)

    out = await auth_mod.require_scopes(["videos:read"], cred())
    assert out["scopes"] == ["videos:read", "videos:write"]

@pytest.mark.asyncio
async def test_require_scopes_sucesso_string_espacada(monkeypatch):
    async def fake_require_user(_cred):
        return {"scope": "videos:read videos:write"}

    monkeypatch.setattr(auth_mod, "require_user", fake_require_user, raising=True)

    out = await auth_mod.require_scopes(["videos:write"], cred())
    assert "scope" in out

@pytest.mark.asyncio
async def test_require_scopes_insuficiente(monkeypatch):
    async def fake_require_user(_cred):
        return {"scopes": ["videos:read"]}

    monkeypatch.setattr(auth_mod, "require_user", fake_require_user, raising=True)

    with pytest.raises(auth_mod.HTTPException) as ex:
        await auth_mod.require_scopes(["videos:write"], cred())
    assert ex.value.status_code == 403
    assert "Escopo insuficiente" in ex.value.detail

# ---------- _safe_token_id ----------

def test_safe_token_id_deterministico():
    t1 = auth_mod._safe_token_id("secret-token")
    t2 = auth_mod._safe_token_id("secret-token")
    assert t1 == t2
    assert len(t1) == 8
    assert t1 != "secret-token"
    assert t1 == hashlib.sha1(b"secret-token").hexdigest()[:8]
