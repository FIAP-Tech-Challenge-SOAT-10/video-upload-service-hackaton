import pytest
from types import SimpleNamespace
from fastapi import HTTPException

import app.core.auth as auth_mod


@pytest.fixture(autouse=True)
def reset_global(monkeypatch):
    # garante estado limpo entre os testes
    monkeypatch.setattr(auth_mod, "auth_client", None, raising=False)
    yield
    auth_mod.auth_client = None


def test_returns_cached_instance_when_already_set(monkeypatch):
    class CachedClient:
        pass

    cached = CachedClient()
    # agora o cache é em auth_client
    monkeypatch.setattr(auth_mod, "auth_client", cached, raising=False)

    got = auth_mod._ensure_client()
    assert got is cached  # deve retornar o cache e NÃO tentar ler settings


def test_initializes_from_settings_and_caches(monkeypatch):
    # 1) settings com os campos que a função espera
    import app.config as cfg
    monkeypatch.setattr(
        cfg,
        "settings",
        SimpleNamespace(
            auth_base_url="http://auth:8000",
            auth_timeout_seconds=7,
            auth_cache_ttl_seconds=120,
        ),
        raising=False,
    )

    # 2) Fake AuthClient no próprio módulo sob teste (import no topo)
    created = {}

    class FakeAuthClient:
        def __init__(self, base_url, timeout_seconds, cache_ttl):
            created["base_url"] = base_url
            created["timeout_seconds"] = timeout_seconds
            created["cache_ttl"] = cache_ttl

    monkeypatch.setattr(auth_mod, "AuthClient", FakeAuthClient, raising=True)

    # 3) Chama e valida (cache deve ser mantido)
    c1 = auth_mod._ensure_client()
    c2 = auth_mod._ensure_client()
    assert isinstance(c1, FakeAuthClient)
    assert c2 is c1
    assert created == {
        "base_url": "http://auth:8000",
        "timeout_seconds": 7,
        "cache_ttl": 120,
    }


def test_settings_failure_returns_503_and_logs(caplog, monkeypatch):
    import app.config as cfg

    class BoomSettings:
        def __getattr__(self, name):
            raise RuntimeError("boom")

    monkeypatch.setattr(cfg, "settings", BoomSettings(), raising=False)

    with caplog.at_level("ERROR"):
        with pytest.raises(HTTPException) as ex:
            auth_mod._ensure_client()

    assert ex.value.status_code == 503
    assert any("Falha ao carregar settings" in rec.getMessage() for rec in caplog.records)


def test_missing_base_url_returns_503_and_logs(caplog, monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(
        cfg,
        "settings",
        SimpleNamespace(
            auth_base_url="",            # ausente/vazio
            auth_timeout_seconds=5,
            auth_cache_ttl_seconds=60,
        ),
        raising=False,
    )

    with caplog.at_level("ERROR"):
        with pytest.raises(HTTPException) as ex:
            auth_mod._ensure_client()

    assert ex.value.status_code == 503
    assert any("AUTH_BASE_URL ausente" in rec.getMessage() for rec in caplog.records)
