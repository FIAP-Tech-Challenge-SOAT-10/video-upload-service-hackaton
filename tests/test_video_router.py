import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.repositories.video_repository_interface import IVideoRepository
from app.routers import videos as videos_router


class FakeRepo(IVideoRepository):
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


@pytest.fixture(autouse=True)
def override_repo():
    app.dependency_overrides[videos_router.get_video_repo] = lambda: FakeRepo()
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_get_status_returns_fake_repo_data():
    resp = client.get("/videos/1234")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id_video"] == "1234"
    assert body["status"] == "UPLOADED"
