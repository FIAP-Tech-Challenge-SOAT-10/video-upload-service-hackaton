import os
from pydantic import BaseModel

class Settings(BaseModel):
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_endpoint_url: str | None = os.getenv("AWS_ENDPOINT_URL")
    s3_bucket: str = os.getenv("S3_BUCKET", "video-service-bucket")
    ddb_table: str = os.getenv("DDB_TABLE", "videos")
    sqs_queue_url: str = os.getenv("SQS_QUEUE_URL", "")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "200"))

settings = Settings()
