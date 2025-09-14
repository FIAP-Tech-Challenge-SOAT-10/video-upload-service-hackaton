import io
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import videos as videos_router
from app.domain.repositories.video_repository_interface import IVideoRepository


@pytest.fixture
def client_no_raise():
    # Não propaga exceções do servidor para o pytest: retorna 500
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ========= Repositórios fakes para controlar respostas =========

class FakeRepoOK(IVideoRepository):
    def __init__(self):
        self.saved = None
        self.last_status = None

    def put(self, item: dict) -> None:
        self.saved = item

    def get(self, id_video: str):
        return {
            "id_video": id_video,
            "titulo": "fake",
            "autor": "fake",
            "status": "UPLOADED",
            "file_path": "s3://bucket/fake",
            "data_criacao": "2025-09-07T00:00:00",
            "data_upload": "2025-09-07T00:00:00",
        }

    def update_status(self, id_video: str, status: str) -> None:
        self.last_status = (id_video, status)


class FakeRepoNotFound(IVideoRepository):
    def put(self, item: dict) -> None:
        pass
    def get(self, id_video: str):
        return None
    def update_status(self, id_video: str, status: str) -> None:
        pass


class FakeRepoZipNone(FakeRepoOK):
    def get(self, id_video: str):
        d = super().get(id_video)
        d.pop("zip_path", None)
        d.pop("s3_key_zip", None)
        return d


class FakeRepoZipInvalid(FakeRepoOK):
    def get(self, id_video: str):
        d = super().get(id_video)
        d["zip_path"] = "not-an-s3-url"
        return d


class FakeRepoZipOK(FakeRepoOK):
    def get(self, id_video: str):
        d = super().get(id_video)
        d["zip_path"] = "s3://bucket/path/to/file.zip"
        return d


# ========= Fixture padrão: repo OK =========
@pytest.fixture(autouse=True)
def override_repo():
    app.dependency_overrides[videos_router.get_video_repo] = lambda: FakeRepoOK()
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


# ========= GET /videos/{id} =========

def test_get_status_ok():
    resp = client.get("/videos/abc123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id_video"] == "abc123"
    assert body["status"] == "UPLOADED"


def test_get_status_not_found():
    # troca somente para este teste
    app.dependency_overrides[videos_router.get_video_repo] = lambda: FakeRepoNotFound()
    resp = client.get("/videos/naoexiste")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vídeo não encontrado"


# ========= POST /videos/upload =========

def test_upload_success(monkeypatch):
    # configura settings
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_mb", 200, raising=False)
    monkeypatch.setattr(settings, "s3_bucket", "video-service-bucket", raising=False)
    monkeypatch.setattr(settings, "sqs_queue_url", "http://localhost:4566/000000000000/queue", raising=False)

    # chave S3 determinística
    monkeypatch.setattr(videos_router, "build_s3_key", lambda fname: ("folder", "folder/my.mp4"))

    # mock S3 put
    calls = {}
    def fake_put_object(bucket, key, data, content_type):
        calls.update(dict(bucket=bucket, key=key, data=data, content_type=content_type))
    monkeypatch.setattr(videos_router, "put_object", fake_put_object, raising=True)

    # mock SQS ok
    class _SQS:
        def send_message(self, **kwargs):
            calls["sqs"] = kwargs
    monkeypatch.setattr(videos_router, "sqs", _SQS(), raising=True)

    files = {
        "file": ("video.mp4", b"\x00\x01\x02", "video/mp4"),
    }
    data = {"titulo": " Meu vídeo ", "autor": " Iana "}
    resp = client.post("/videos/upload", files=files, data=data)
    assert resp.status_code == 202, resp.text

    body = resp.json()
    assert body["titulo"] == "Meu vídeo"
    assert body["autor"] == "Iana"
    assert body["s3_key"] == "folder/my.mp4"

    # asserts de IO
    assert calls["bucket"] == "video-service-bucket"
    assert calls["key"] == "folder/my.mp4"
    assert calls["data"] == b"\x00\x01\x02"
    assert calls["content_type"] == "video/mp4"
    assert "MessageBody" in calls["sqs"]


def test_upload_unsupported_mime():
    files = {"file": ("file.txt", b"hello", "text/plain")}
    data = {"titulo": "t", "autor": "a"}
    resp = client.post("/videos/upload", files=files, data=data)
    assert resp.status_code == 415
    assert "não suportado" in resp.json()["detail"].lower()


def test_upload_too_large(monkeypatch):
    from app.config import settings
    # limite 0 MB para forçar 413
    monkeypatch.setattr(settings, "max_upload_mb", 0, raising=False)

    files = {"file": ("big.mp4", b"abc", "video/mp4")}
    data = {"titulo": "t", "autor": "a"}
    resp = client.post("/videos/upload", files=files, data=data)
    assert resp.status_code == 413
    assert "excede" in resp.json()["detail"].lower()


def test_upload_storage_failure(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_mb", 200, raising=False)
    monkeypatch.setattr(settings, "s3_bucket", "video-service-bucket", raising=False)

    monkeypatch.setattr(videos_router, "build_s3_key", lambda fname: ("f", "f/x.mp4"))
    def boom(*args, **kwargs):
        raise RuntimeError("S3 down")
    monkeypatch.setattr(videos_router, "put_object", boom, raising=True)

    files = {"file": ("video.mp4", b"1", "video/mp4")}
    data = {"titulo": "t", "autor": "a"}
    resp = client.post("/videos/upload", files=files, data=data)
    assert resp.status_code == 502
    assert "Falha ao salvar no storage" in resp.json()["detail"]


def test_upload_sqs_failure(monkeypatch, client_no_raise):
    from app.config import settings
    monkeypatch.setattr(settings, "max_upload_mb", 200, raising=False)
    monkeypatch.setattr(settings, "s3_bucket", "video-service-bucket", raising=False)
    monkeypatch.setattr(settings, "sqs_queue_url", "http://localhost:4566/000000000000/queue", raising=False)
    monkeypatch.setattr(videos_router, "build_s3_key", lambda fname: ("f", "f/x.mp4"))
    monkeypatch.setattr(videos_router, "put_object", lambda *a, **k: None, raising=True)

    class _SQS:
        def send_message(self, **kwargs):
            raise RuntimeError("SQS indisponível")
    monkeypatch.setattr(videos_router, "sqs", _SQS(), raising=True)

    files = {"file": ("video.mp4", b"1", "video/mp4")}
    data = {"titulo": "t", "autor": "a"}

    # Usa o client que não levanta a exceção – retorna 500
    resp = client_no_raise.post("/videos/upload", files=files, data=data)
    assert resp.status_code == 500

# ========= GET /videos/download/{id} =========

def test_get_download_not_found():
    app.dependency_overrides[videos_router.get_video_repo] = lambda: FakeRepoNotFound()
    resp = client.get("/videos/download/naoexiste")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vídeo não encontrado"


def test_get_download_no_zip_conflict():
    app.dependency_overrides[videos_router.get_video_repo] = lambda: FakeRepoZipNone()
    resp = client.get("/videos/download/abc")
    assert resp.status_code == 409
    assert "Processamento" in resp.json()["detail"]


def test_get_download_invalid_zip_path():
    app.dependency_overrides[videos_router.get_video_repo] = lambda: FakeRepoZipInvalid()
    resp = client.get("/videos/download/abc")
    assert resp.status_code == 400
    assert "inválido" in resp.json()["detail"].lower()


def test_get_download_success(monkeypatch):
    app.dependency_overrides[videos_router.get_video_repo] = lambda: FakeRepoZipOK()

    class _S3:
        def generate_presigned_url(self, *args, **kwargs):
            return "https://signed.example/url"
    # monkeypatch no client S3 do módulo
    monkeypatch.setattr(videos_router, "s3", _S3(), raising=True)

    resp = client.get("/videos/download/abc")
    assert resp.status_code == 200
    assert resp.json()["presigned_url"] == "https://signed.example/url"
