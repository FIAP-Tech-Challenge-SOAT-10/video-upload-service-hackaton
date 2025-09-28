import os
import boto3
import uuid
import pytest

from app.infrastructure.repositories.video_repo import VideoRepo
import app.infrastructure.repositories.video_repo as repo_mod
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

def _put(table, item):
    table.put_item(Item=item)

def test_list_by_user_ok(videos_table):
    repo = VideoRepo()
    user_id = f"test-{uuid.uuid4()}"   # <-- user_id único

    # seed só do usuário único
    _put(videos_table, {"id_video": "v1", "id": user_id, "titulo": "A"})
    _put(videos_table, {"id_video": "v2", "id": user_id, "titulo": "B"})
    _put(videos_table, {"id_video": "v3", "id": "alguem-else", "titulo": "C"})

    items = repo.list_by_user(user_id=user_id)  # método converte pra str se necessário
    ids = sorted([i["id_video"] for i in items])
    assert ids == ["v1", "v2"]

def test_list_by_user_error_path(monkeypatch):
    repo = VideoRepo()

    class BrokenTable:
        def scan(self, *a, **k):
            raise RuntimeError("boom")

    # patch no MÓDULO do repositório, não em app.aws
    monkeypatch.setattr(repo_mod.aws_mod, "table_videos", BrokenTable(), raising=True)

    with pytest.raises(RuntimeError):
        repo.list_by_user(user_id="qualquer")
