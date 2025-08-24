from typing import Tuple
from ..config import settings
from ..aws import s3
from .id_gen import new_id

def build_s3_key(original_filename: str, vid: str | None = None) -> Tuple[str, str]:
    vid = vid or new_id()
    key = f"videos/{vid}/{original_filename}"
    return vid, key

def put_object(bucket: str, key: str, file_bytes: bytes, content_type: str) -> None:
    s3.put_object(Bucket=bucket, Key=key, Body=file_bytes, ContentType=content_type)
