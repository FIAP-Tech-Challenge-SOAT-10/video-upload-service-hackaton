# app/infrastructure/repositories/video_repo.py
from datetime import datetime
from app.domain.repositories.video_repository_interface import IVideoRepository
import app.aws as aws_mod   # <-- importe o módulo, não o símbolo

from app.core.metrics import DDB_OPS
from typing import List
from boto3.dynamodb.conditions import Attr, Key


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

    def list_by_user(self, user_id) -> List[dict]:
        """
        Retorna todos os vídeos cujo atributo 'id' == user_id (do token).
        Observação: Scan + Filter; troque por Query com GSI para produção.
        """
        user_id = str(user_id)
        
        try:
            resp = aws_mod.table_videos.scan(
                FilterExpression=Attr("id").eq(user_id)  # se preferir por email, use Attr("email").eq(email)
            )
            DDB_OPS.labels(op="scan", status="ok").inc()
            return resp.get("Items", [])
        except Exception:
            DDB_OPS.labels(op="scan", status="error").inc()
            raise