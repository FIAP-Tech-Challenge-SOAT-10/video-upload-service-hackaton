from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# HTTP
REQUESTS = Counter("http_requests_total", "HTTP requests", ["path", "method", "status"])
LATENCY  = Histogram(
    "http_request_duration_seconds", "HTTP request duration (s)", ["path", "method"],
    buckets=(0.05,0.1,0.2,0.5,1,2,5,10)
)

# Domínio
UPLOAD_BYTES = Counter("video_upload_bytes_total", "Total bytes received in uploads")
S3_OPS = Counter("s3_operations_total", "S3 operations", ["op","status"])                 # op: put,get,sign
SQS_OPS = Counter("sqs_operations_total", "SQS operations", ["op","status"])              # op: send,receive,delete
DDB_OPS = Counter("dynamodb_operations_total", "DynamoDB operations", ["op","status"])    # op: put,get,update,query

router_metrics = APIRouter()
@router_metrics.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
