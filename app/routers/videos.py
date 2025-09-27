# app/routers/videos.py
import uuid
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import settings
from ..domain.models.video import VideoItem
from ..domain.models.response import UploadResponse, StatusResponse
from ..domain.repositories.video_repository_interface import IVideoRepository
from ..infrastructure.repositories.video_repo import VideoRepo
from ..utils.s3 import build_s3_key, put_object
from ..aws import sqs, s3

from app.core.metrics import UPLOAD_BYTES, SQS_OPS
from typing import Dict, Any
from app.auth import require_user

import logging

router = APIRouter(
    prefix="/videos",
    tags=["videos"],
    dependencies=[Depends(require_user)]
)

ALLOWED_MIME_PREFIX = "video/"
bearer = HTTPBearer()  


def get_video_repo() -> IVideoRepository:
    return VideoRepo()

logger = logging.getLogger("videos")

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_video(
    titulo: str = Form(..., max_length=200),
    autor: str = Form(..., max_length=100),
    file: UploadFile = File(...),
    repo: IVideoRepository = Depends(get_video_repo),
    _sec: HTTPAuthorizationCredentials = Security(bearer),  # expõe o esquema no OpenAPI
    _token: str = Depends(require_user),                     # valida de verdade o token
) -> UploadResponse:
    id_video = str(uuid.uuid4())

    if not (file.content_type or "").startswith(ALLOWED_MIME_PREFIX):
        raise HTTPException(status_code=415, detail="Tipo de arquivo não suportado (esperado video/*)")

    data = await file.read()
    UPLOAD_BYTES.inc(len(data))

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Arquivo excede limite de {settings.max_upload_mb}MB")

    _, key = build_s3_key(file.filename)
    try:
        put_object(settings.s3_bucket, key, data, file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Falha ao salvar no storage: {e}")

    now = datetime.utcnow()
    item = VideoItem(
        id_video=id_video,
        titulo=titulo.strip(),
        autor=autor.strip(),
        status="UPLOADED",
        file_path=f"s3://{settings.s3_bucket}/{key}",
        data_criacao=now,
        data_upload=now,
        email=_token.email,
        username=_token.username,
        id=_token.id,
    )

    repo.put(item.model_dump(mode="json"))

    logger.info(f"Enviando mensagem SQS para processamento: {item.model_dump_json()}")

    try:
        sqs.send_message(QueueUrl=settings.sqs_queue_url, MessageBody=item.model_dump_json())
        logger.info(f"Message Body: {item.model_dump_json()}")
        SQS_OPS.labels(op="send", status="ok").inc()
    except Exception:
        SQS_OPS.labels(op="send", status="error").inc()
        raise

    return UploadResponse(
        id_video=item.id_video,
        titulo=item.titulo,
        autor=item.autor,
        status=item.status,
        s3_key=key,
        links={
            "status": f"/videos/{item.id_video}",
            "download": f"/videos/download/{item.id_video}",
        },
        email=item.email,
        username=item.username,
        id=item.id,
    )

@router.get("/{id_video}", response_model=StatusResponse)
def get_status(
    id_video: str,
    repo: IVideoRepository = Depends(get_video_repo),
    _sec: HTTPAuthorizationCredentials = Security(bearer),
    _token: str = Depends(require_user),
) -> StatusResponse:
    item = repo.get(id_video)
    if not item:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    return StatusResponse(**item)

@router.get("/download/{video_id}")
def get_download(
    video_id: str,
    repo: IVideoRepository = Depends(get_video_repo),
    _sec: HTTPAuthorizationCredentials = Security(bearer),
    _token: str = Depends(require_user),
):
    item = repo.get(video_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    zip_path = item.get("zip_path") or item.get("s3_key_zip")
    if not zip_path:
        raise HTTPException(status_code=409, detail="Processamento ainda não finalizado ou ZIP indisponível")
    if not zip_path.startswith("s3://"):
        raise HTTPException(status_code=400, detail="zip_path inválido")

    parsed = urlparse(zip_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=900,
    )
    return {"presigned_url": url}
