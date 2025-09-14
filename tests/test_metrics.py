import re
from typing import Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

import app.core.metrics as m


# ---------- helpers ----------

def _metrics_text() -> str:
    """Captura o payload atual do Prometheus default registry."""
    return generate_latest().decode("utf-8", errors="ignore")


def _series_value(text: str, metric: str, labels: Dict[str, str] | None = None, suffix: str = "") -> float:
    """
    Retorna o valor numérico de uma série (counter/gauge/histogram_count) no exposition format.
    - labels: se fornecido, a série deve conter todos esses pares k="v"
    - suffix: ex.: "_count" para histograma
    Retorna 0.0 se a série ainda não existir.
    """
    target = metric + suffix
    # percorre linhas de amostra (ignora HELP/TYPE)
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        if not line.startswith(target):
            continue
        if labels:
            # exige que todos os pares apareçam na linha (ordem não importa)
            if not all(f'{k}="{v}"' in line for k, v in labels.items()):
                continue
        # extrai o último token como número
        try:
            val = float(line.split()[-1])
            return val
        except Exception:
            continue
    return 0.0


# ---------- tests ----------

def test_metrics_endpoint_ok():
    app = FastAPI()
    app.include_router(m.router_metrics)

    with TestClient(app) as client:
        r = client.get("/metrics")
        assert r.status_code == 200
        # content-type padrão do Prometheus
        assert "text/plain" in r.headers.get("content-type", "")
        # deve haver linhas HELP/TYPE de algum dos seus métricos
        assert "# HELP http_requests_total" in r.text or "# TYPE http_requests_total" in r.text


def test_counters_and_histogram_register_increments():
    # Snapshot antes
    before = _metrics_text()

    # -------- Counters sem/with labels
    # UPLOAD_BYTES (sem labels)
    base_upload = _series_value(before, "video_upload_bytes_total")
    m.UPLOAD_BYTES.inc(7)
    after = _metrics_text()
    assert _series_value(after, "video_upload_bytes_total") >= base_upload + 7

    # REQUESTS (labels: path, method, status)
    labels_req = {"path": "/x", "method": "GET", "status": "200"}
    base_req = _series_value(before, "http_requests_total", labels_req)
    m.REQUESTS.labels(**labels_req).inc()
    after = _metrics_text()
    assert _series_value(after, "http_requests_total", labels_req) >= base_req + 1

    # S3_OPS (labels: op, status)
    labels_s3 = {"op": "put", "status": "ok"}
    base_s3 = _series_value(before, "s3_operations_total", labels_s3)
    m.S3_OPS.labels(**labels_s3).inc(2)
    after = _metrics_text()
    assert _series_value(after, "s3_operations_total", labels_s3) >= base_s3 + 2

    # SQS_OPS
    labels_sqs = {"op": "send", "status": "ok"}
    base_sqs = _series_value(before, "sqs_operations_total", labels_sqs)
    m.SQS_OPS.labels(**labels_sqs).inc()
    after = _metrics_text()
    assert _series_value(after, "sqs_operations_total", labels_sqs) >= base_sqs + 1

    # DDB_OPS
    labels_ddb = {"op": "put", "status": "ok"}
    base_ddb = _series_value(before, "dynamodb_operations_total", labels_ddb)
    m.DDB_OPS.labels(**labels_ddb).inc()
    after = _metrics_text()
    assert _series_value(after, "dynamodb_operations_total", labels_ddb) >= base_ddb + 1

    # -------- Histogram LATENCY (labels: path, method) — checamos o *_count
    labels_lat = {"path": "/lat", "method": "POST"}
    base_count = _series_value(before, "http_request_duration_seconds", labels_lat, suffix="_count")
    m.LATENCY.labels(**labels_lat).observe(0.12)
    after = _metrics_text()
    assert _series_value(after, "http_request_duration_seconds", labels_lat, suffix="_count") >= base_count + 1

    # (opcional) também dá pra checar um bucket específico apareceu
    assert any(
        line.startswith('http_request_duration_seconds_bucket')
        and 'le="0.2"' in line
        and f'path="{labels_lat["path"]}"' in line
        and f'method="{labels_lat["method"]}"' in line
        for line in after.splitlines()
    )
