# routers/videos.py
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from datetime import datetime
from urllib.parse import urlparse

from ..config import settings
from ..domain.models.video import VideoItem
from ..domain.models.response import UploadResponse, StatusResponse 
from ..repositories.video_repo import VideoRepo
from ..utils.s3 import build_s3_key, put_object
from ..aws import sqs, s3

router = APIRouter(prefix="/videos", tags=["videos"])

ALLOWED_MIME_PREFIX = "video/"  # simples e eficaz pra v1

@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_video(
    titulo: str = Form(..., max_length=200),
    autor: str = Form(..., max_length=100),
    file: UploadFile = File(...)
):
    # gera automaticamente um id único para o vídeo
    id_video = str(uuid.uuid4())

    # status inicial definido internamente (não aparece no Swagger)
    status_inicial = "PENDENTE"

    # validação leve de content type e tamanho
    if not (file.content_type or "").startswith(ALLOWED_MIME_PREFIX):
        raise HTTPException(status_code=415, detail="Tipo de arquivo não suportado (esperado video/*)")
    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Arquivo excede limite de {settings.max_upload_mb}MB")

    # grava no S3
    _, key = build_s3_key(file.filename)
    try:
        put_object(settings.s3_bucket, key, data, file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Falha ao salvar no storage: {e}")

    # registra no DynamoDB
    now = datetime.utcnow()
    item = VideoItem(
        id_video=id_video,
        titulo=titulo.strip(),
        autor=autor.strip(),
        status="UPLOADED",  # você pode manter "PENDENTE" aqui se preferir
        file_path=f"s3://{settings.s3_bucket}/{key}",
        data_criacao=now,
        data_upload=now,
    )

    # salva metadados (ISO-8601 via mode="json")
    VideoRepo.put(item.model_dump(mode="json"))

    # publica mensagem para processamento (próxima etapa)
    try:
        response = sqs.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=item.model_dump_json()
        )
        print(f"[SQS] Mensagem enviada com sucesso: MessageId={response.get('MessageId')}")
    except Exception as e:
        print(f"[SQS] Falha ao enviar mensagem: {e}")
        # não falha o upload; apenas não enfileirou
        pass

    # resposta 202 com links úteis
    return UploadResponse(
        id_video=item.id_video,
        titulo=item.titulo,
        autor=item.autor,
        status=item.status,  # "UPLOADED" (ou "PENDENTE", se você preferir manter)
        s3_key=key,
        links={
            "status": f"/videos/status/{item.id_video}",
            "download": f"/videos/download/{item.id_video}"
        }
    )


@router.get("/status/{id_video}", response_model=StatusResponse)
def get_status(id_video: str):
    item = VideoRepo.get(id_video)
    if not item:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    return StatusResponse(**item)


@router.get("/download/{video_id}")
def get_download(video_id: str):
    """Opcional nesta v1: presigned URL para baixar o arquivo original."""
    item = VideoRepo.get(video_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vídeo não encontrado")
    fp = item.get("file_path")
    if not fp or not fp.startswith("s3://"):
        raise HTTPException(status_code=400, detail="file_path inválido")
    parsed = urlparse(fp)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=900,  # 15 min
    )
    return {"presigned_url": url}
