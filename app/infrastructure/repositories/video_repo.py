# app/infrastructure/repositories/video_repo.py
from datetime import datetime
from app.domain.repositories.video_repository_interface import IVideoRepository
import app.aws as aws_mod   # <-- importe o módulo, não o símbolo

from app.core.metrics import DDB_OPS


class VideoRepo(IVideoRepository):
    def put(self, item: dict) -> None:
        try:
            aws_mod.table_videos.put_item(Item=item)
            DDB_OPS.labels(op="put", status="ok").inc()
        except Exception:
            DDB_OPS.labels(op="put", status="error").inc()
            raise
        

    def get(self, id_video: str) -> dict | None:
        resp = aws_mod.table_videos.get_item(Key={"id_video": id_video})
        return resp.get("Item")

    def update_status(self, id_video: str, status: str) -> None:
        aws_mod.table_videos.update_item(
            Key={"id_video": id_video},
            UpdateExpression="SET #s = :s, data_upload = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": status, ":u": datetime.utcnow().isoformat()},
        )
