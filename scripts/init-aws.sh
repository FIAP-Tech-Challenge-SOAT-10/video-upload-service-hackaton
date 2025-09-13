#!/usr/bin/env bash
set -euo pipefail

: "${AWS_DEFAULT_REGION:=us-east-1}"
: "${S3_BUCKET:=video-service-bucket}"
: "${SQS_QUEUE_NAME:=video-processing-queue}"
: "${DDB_TABLE:=videos}"

echo "[init] criando bucket S3: s3://$S3_BUCKET"
awslocal s3 ls "s3://$S3_BUCKET" >/dev/null 2>&1 || awslocal s3 mb "s3://$S3_BUCKET"

echo "[init] criando fila SQS: $SQS_QUEUE_NAME"
awslocal sqs get-queue-url --queue-name "$SQS_QUEUE_NAME" >/dev/null 2>&1 \
  || awslocal sqs create-queue --queue-name "$SQS_QUEUE_NAME" >/dev/null

# Se já existir uma tabela com outro schema, apague. (Opcional, mas útil em dev)
if awslocal dynamodb describe-table --table-name "$DDB_TABLE" >/dev/null 2>&1; then
  KEY_ATTR=$(awslocal dynamodb describe-table --table-name "$DDB_TABLE" \
    --query 'Table.KeySchema[0].AttributeName' --output text || echo "")
  if [ "$KEY_ATTR" != "id_video" ]; then
    echo "[init] tabela $DDB_TABLE existe com PK '$KEY_ATTR' != 'id_video' — recriando"
    awslocal dynamodb delete-table --table-name "$DDB_TABLE"
    until awslocal dynamodb list-tables >/dev/null 2>&1; do sleep 1; done
  fi
fi

echo "[init] garantindo tabela DynamoDB: $DDB_TABLE (PK=id_video)"
awslocal dynamodb describe-table --table-name "$DDB_TABLE" >/dev/null 2>&1 || \
awslocal dynamodb create-table \
  --table-name "$DDB_TABLE" \
  --attribute-definitions AttributeName=id_video,AttributeType=S \
  --key-schema AttributeName=id_video,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST >/dev/null

echo "[init] pronto."
