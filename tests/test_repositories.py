import uuid
from datetime import datetime, timezone

import pytest

# Importa o repo concreto e o módulo onde vive `table_videos`
from app.infrastructure.repositories.video_repo import VideoRepo
import app.aws as aws_mod


@pytest.fixture(autouse=True)
def patch_table_videos(videos_table):
    """
    Substitui o `table_videos` usado pelo repositório pela tabela criada no LocalStack.
    Isso evita tocar em recursos reais e mantém o contrato intacto.
    """
    original = getattr(aws_mod, "table_videos", None)
    aws_mod.table_videos = videos_table
    try:
        yield
    finally:
        if original is not None:
            aws_mod.table_videos = original


def test_put_and_get_video(videos_table):
    repo = VideoRepo()

    id_video = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    item = {
        "id_video": id_video,
        "titulo": "Video de Teste",
        "autor": "Iana",
        "status": "UPLOADED",
        "file_path": "s3://video-service-bucket/test.mp4",
        "data_criacao": now,
        "data_upload": now,
        "email": "user@example.com",
        "username": "tester",
        "id": str("123"),
    }

    # put
    repo.put(item)

    # get
    fetched = repo.get(id_video)
    assert fetched is not None
    assert fetched["id_video"] == id_video
    assert fetched["status"] == "UPLOADED"
    assert fetched["file_path"].startswith("s3://")


def test_update_status(videos_table):
    repo = VideoRepo()

    id_video = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Seed
    repo.put(
        {
            "id_video": id_video,
            "titulo": "Seed",
            "autor": "Teste",
            "status": "PENDENTE",
            "file_path": "s3://bucket/seed.mp4",
            "data_criacao": now,
            "data_upload": now,
        }
    )

    # Atualiza
    repo.update_status(id_video, "PROCESSANDO")

    # Verifica
    got = repo.get(id_video)
    assert got is not None
    assert got["status"] == "PROCESSANDO"
    # Confere que data_upload foi atualizada para um ISO-8601
    assert "data_upload" in got and isinstance(got["data_upload"], str)
    assert "T" in got["data_upload"]  # heurística simples de ISO
