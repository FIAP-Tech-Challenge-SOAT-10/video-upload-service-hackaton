#!/usr/bin/env bash
set -euo pipefail

awslocal s3 mb s3://video-service-bucket || true

awslocal dynamodb create-table \
  --table-name videos \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST || true

awslocal sqs create-queue --queue-name video-processing-queue || true

awslocal s3 ls
awslocal dynamodb list-tables
awslocal sqs list-queues
