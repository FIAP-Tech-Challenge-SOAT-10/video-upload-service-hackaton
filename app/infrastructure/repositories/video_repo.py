from datetime import datetime
from app.domain.repositories.video_repository_interface import IVideoRepository
from app.utils.aws import table_videos

class VideoRepo:
    @staticmethod
    def put(item: dict):
        table_videos.put_item(Item=item)

    @staticmethod
    def get(id_video: str) -> dict | None:
        resp = table_videos.get_item(Key={"id_video": id_video})
        return resp.get("Item")

    @staticmethod
    def update_status(id_video: str, status: str):
        table_videos.update_item(
            Key={"id_video": id_video},
            UpdateExpression="SET #s = :s, data_upload = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": status,
                ":u": datetime.utcnow().isoformat(),
            },
        )
