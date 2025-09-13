import os
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

_session = boto3.session.Session()

_s3 = _session.client(
    "s3",
    endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566"),
    region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    config=Config(
        s3={"addressing_style": "path"},  # evita issues de virtual-host no LocalStack
        retries={"max_attempts": 10, "mode": "standard"}
    ),
)

_BUCKET = os.getenv("S3_BUCKET", "video-service-bucket")


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    try:
        _s3.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        # Retorna a URL "estilo path" do LocalStack (útil para logs, não é pública)
        return f"{os.getenv('AWS_ENDPOINT_URL','http://localstack:4566')}/{_BUCKET}/{key}"
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Falha ao salvar no storage: {e}")
