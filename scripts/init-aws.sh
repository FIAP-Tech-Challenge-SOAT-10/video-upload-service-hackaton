#!/usr/bin/env bash
set -euo pipefail

: "${AWS_DEFAULT_REGION:=us-east-1}"
: "${S3_BUCKET:=video-service-bucket}"
: "${SQS_QUEUE_NAME:=video-processing-queue}"
: "${DDB_TABLE:=videos}"

echo "[init] criando bucket S3: s3://$S3_BUCKET"
awslocal s3 ls "s3://$S3_BUCKET" >/dev/null 2>&1 || awslocal s3 mb "s3://$S3_BUCKET"

echo "[init] criando fila SQS: $SQS_QUEUE_NAME"
awslocal sqs create-queue --queue-name "$SQS_QUEUE_NAME" >/dev/null 2>&1 || true

echo "[init] criando tabela DynamoDB: $DDB_TABLE"
awslocal dynamodb create-table \
  --table-name "$DDB_TABLE" \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST >/dev/null 2>&1 || true

echo "[init] pronto."
echo "Você pode iniciar o serviço com: docker-compose up -d"