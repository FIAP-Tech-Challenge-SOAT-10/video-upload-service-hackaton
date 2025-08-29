from ..aws import table_videos
from datetime import datetime

class VideoRepo:
    @staticmethod
    def put(item: dict):
        table_videos.put_item(Item=item)

    @staticmethod
    def get(video_id: str) -> dict | None:
        resp = table_videos.get_item(Key={"id_video": id_video})
        return resp.get("Item")

    @staticmethod
    def update_status(video_id: str, status: str):
        table_videos.update_item(
            Key={"id_video": id_video},
            UpdateExpression="SET #s = :s, data_upload = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":s": status,
                ":u": datetime.utcnow().isoformat(),
            },
        )
