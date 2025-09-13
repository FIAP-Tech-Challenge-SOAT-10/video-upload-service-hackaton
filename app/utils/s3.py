from typing import Tuple
from ..config import settings
from ..aws import s3
from .id_gen import new_id
from app.core.metrics import S3_OPS

def build_s3_key(original_filename: str, vid: str | None = None) -> Tuple[str, str]:
     vid = vid or new_id()
     key = f"videos/{vid}/{original_filename}"
     return vid, key

def put_object(bucket: str, key: str, file_bytes: bytes, content_type: str) -> None:
    """Envia o objeto ao S3 e incrementa métricas de sucesso/erro."""
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=file_bytes, ContentType=content_type)
        S3_OPS.labels(op="put", status="ok").inc()
    except Exception:
        S3_OPS.labels(op="put", status="error").inc()
        raise