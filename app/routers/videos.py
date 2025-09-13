# app/routers/videos.py
import uuid
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends

from ..config import settings
from ..domain.models.video import VideoItem
from ..domain.models.response import UploadResponse, StatusResponse
from ..domain.repositories.video_repository_interface import IVideoRepository
from ..infrastructure.repositories.video_repo import VideoRepo
from ..utils.s3 import build_s3_key, put_object
from ..aws import sqs, s3

from app.core.metrics import UPLOAD_BYTES, SQS_OPS

router = APIRouter(prefix="/videos", tags=["videos"])

ALLOWED_MIME_PREFIX = "video/"


# Provider simples para injeção
def get_video_repo() -> IVideoRepository:
    return VideoRepo()


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_video(
    titulo: str = Form(..., max_length=200),
    autor: str = Form(..., max_length=100),
    file: UploadFile = File(...),
    repo: IVideoRepository = Depends(get_video_repo),
) -> UploadResponse:
    id_video = str(uuid.uuid4())

    # validação leve de content type e tamanho
    if not (file.content_type or "").startswith(ALLOWED_MIME_PREFIX):
        raise HTTPException(status_code=415, detail="Tipo de arquivo não suportado (esperado video/*)")

    data = await file.read()
    # Métrica de bytes recebidos (conta tentativa de upload)
    UPLOAD_BYTES.inc(len(data))

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Arquivo excede limite de {settings.max_upload_mb}MB")

    # grava no S3
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
    )

    # salva metadados
    repo.put(item.model_dump(mode="json"))

    # publica mensagem para processamento
    try:
        sqs.send_message(QueueUrl=settings.sqs_queue_url, MessageBody=item.model_dump_json())
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
            "status": f"/videos/{item.id_video}",              # atualizado para o novo endpoint
            "download": f"/videos/download/{item.id_video}",
        },
    )


@router.get("/{id_video}", response_model=StatusResponse)
def get_status(id_video: str, repo: IVideoRepository = Depends(get_video_repo)) -> StatusResponse:
    item = repo.get(id_video)
    if not item:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    return StatusResponse(**item)


@router.get("/download/{video_id}")
def get_download(video_id: str, repo: IVideoRepository = Depends(get_video_repo)):
    item = repo.get(video_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")

    # Preferir o ZIP processado (quando o Processing Service preencher zip_path/s3_key_zip)
    zip_path = item.get("zip_path") or item.get("s3_key_zip")
    if zip_path:
        if not zip_path.startswith("s3://"):
            raise HTTPException(status_code=400, detail="zip_path inválido")
        parsed = urlparse(zip_path)
    else:
        # Se ainda não processou, retorne 409 (ou remova este bloco para baixar o original)
        raise HTTPException(status_code=409, detail="Processamento ainda não finalizado ou ZIP indisponível")

    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=900,
    )
    return {"presigned_url": url}
