import importlib
import pytest
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
import app.main as main

def _fresh_app():
    # garante app.main “limpo” caso outros testes mexam em sys.modules
    import app.main as app_main
    importlib.reload(app_main)
    return app_main

def test_app_metadata_routes_and_cors():
    app_main = _fresh_app()

    # metadados
    assert app_main.app.title == "Video Service"
    assert app_main.app.version == "0.1.0"

    # CORS instalado
    assert any(m.cls is CORSMiddleware for m in app_main.app.user_middleware)

    with TestClient(app_main.app) as client:
        # verifica a rota real em vez de depender do OpenAPI
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

        # OpenAPI deve existir
        r = client.get("/openapi.json")
        assert r.status_code == 200
        paths = r.json().get("paths", {})

        # Deve haver ao menos uma rota de /videos registrada
        assert any(p.startswith("/videos") for p in paths.keys()), f"paths={list(paths.keys())}"

@pytest.fixture
def client():
    # rota de debug não deve exigir auth; se exigir, adicione headers={"Authorization": "Bearer test"}
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_auth_client(monkeypatch):
    # garante estado limpo do _auth_client antes/depois de cada teste
    monkeypatch.setattr(main.core_auth, "_auth_client", None, raising=False)
    yield
    monkeypatch.setattr(main.core_auth, "_auth_client", None, raising=False)


def test_auth_status_uninitialized(client):
    resp = client.get("/debug/auth-status")
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/json")

    body = resp.json()
    assert body["initialized"] is False
    assert body["base_url"] is None
    assert body["timeout"] is None
    assert body["cache_ttl"] is None


def test_auth_status_initialized(client, monkeypatch):
    class FakeAuthClient:
        def __init__(self):
            self._base_url = "http://auth:8000"
            self._timeout = 7
            self._cache_ttl = 30

    # injeta um cliente “inicializado” no mesmo objeto core_auth usado pelo main
    monkeypatch.setattr(main.core_auth, "_auth_client", FakeAuthClient(), raising=False)

    resp = client.get("/debug/auth-status")
    assert resp.status_code == 200

    body = resp.json()
    assert body == {
        "initialized": True,
        "base_url": "http://auth:8000",
        "timeout": 7,
        "cache_ttl": 30,
    }
