#!/usr/bin/env bash
set -euo pipefail

: "${AWS_DEFAULT_REGION:=us-east-1}"
: "${S3_BUCKET:=video-service-bucket}"
: "${SQS_QUEUE_NAME:=video-processing-queue}"
: "${DDB_TABLE:=videos}"
: "${RECREATE_DDB:=0}"   # set RECREATE_DDB=1 para forçar recriação

echo "[init] criando bucket S3: s3://$S3_BUCKET"
awslocal s3 ls "s3://$S3_BUCKET" >/dev/null 2>&1 || awslocal s3 mb "s3://$S3_BUCKET"

echo "[init] criando fila SQS: $SQS_QUEUE_NAME"
awslocal sqs create-queue --queue-name "$SQS_QUEUE_NAME" >/dev/null 2>&1 || true

ensure_ddb() {
  # Se a tabela existe e RECREATE_DDB=1, dropa
  if awslocal dynamodb describe-table --table-name "$DDB_TABLE" >/dev/null 2>&1; then
    if [ "$RECREATE_DDB" = "1" ]; then
      echo "[init] recriando tabela DynamoDB: $DDB_TABLE"
      awslocal dynamodb delete-table --table-name "$DDB_TABLE" >/dev/null
      awslocal dynamodb wait table-not-exists --table-name "$DDB_TABLE"
    else
      # Verifica se a PK é id_video; se não for, alerta
      PK_NAME=$(awslocal dynamodb describe-table --table-name "$DDB_TABLE" \
        --query 'Table.KeySchema[?KeyType==`HASH`].AttributeName' --output text || true)
      if [ "$PK_NAME" != "id_video" ]; then
        echo "[init][WARN] Tabela $DDB_TABLE já existe com PK=$PK_NAME (esperado: id_video)."
        echo "      Use RECREATE_DDB=1 para recriar com o schema correto."
        return
      fi
      echo "[init] tabela DynamoDB já existe com PK=id_video"
      return
    fi
  fi

  echo "[init] criando tabela DynamoDB: $DDB_TABLE (PK=id_video)"
  awslocal dynamodb create-table \
    --table-name "$DDB_TABLE" \
    --attribute-definitions AttributeName=id_video,AttributeType=S \
    --key-schema AttributeName=id_video,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  awslocal dynamodb wait table-exists --table-name "$DDB_TABLE"
}

ensure_ddb

echo "[init] pronto."
echo "Você pode iniciar o serviço com: docker compose up -d"
