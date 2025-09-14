import importlib
import pytest
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

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
