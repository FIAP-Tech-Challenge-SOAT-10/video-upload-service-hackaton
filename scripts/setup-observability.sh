#!/usr/bin/env bash
set -euo pipefail

# Executa a partir da raiz do projeto (pasta do docker-compose.yml)
cd "$(dirname "$0")/.."

echo "[obs] preparando pastas…"
rm -rf observability/grafana/dashboards/dashboards.yml || true
rm -rf observability/grafana/provisioning/dashboards/dashboards.yml || true

mkdir -p observability/prometheus
mkdir -p observability/grafana/datasources
mkdir -p observability/grafana/provisioning/dashboards
mkdir -p observability/grafana/dashboards

# Prometheus scrape config (ajuste o alvo se o nome do serviço não for 'api')
if [ ! -f observability/prometheus/prometheus.yml ]; then
  cat > observability/prometheus/prometheus.yml <<'YAML'
global:
  scrape_interval: 10s
  evaluation_interval: 10s

scrape_configs:
  - job_name: "video-management-api"
    metrics_path: /metrics
    static_configs:
      - targets: ["api:8094"]   # se usar container_name, troque para <container_name>:8094
YAML
  echo "[obs] criado observability/prometheus/prometheus.yml"
else
  echo "[obs] mantendo observability/prometheus/prometheus.yml existente"
fi

# Grafana datasource (Prometheus)
cat > observability/grafana/datasources/datasource.yml <<'YAML'
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prometheus-default
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      httpMethod: GET
YAML
echo "[obs] atualizado observability/grafana/datasources/datasource.yml"

# Grafana provider de dashboards
cat > observability/grafana/provisioning/dashboards/dashboards.yml <<'YAML'
apiVersion: 1
providers:
  - name: "Video Service Dashboards"
    orgId: 1
    folder: ""
    type: file
    allowUiUpdates: true
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /etc/grafana/dashboards
      foldersFromFilesStructure: true
YAML
echo "[obs] atualizado observability/grafana/provisioning/dashboards/dashboards.yml"

# Lembrete do dashboard JSON
DASH_JSON="observability/grafana/dashboards/video-management.json"
if [ ! -f "$DASH_JSON" ]; then
  echo "[obs] ATENÇÃO: salve o dashboard JSON em $DASH_JSON"
  echo "      (use o JSON que te enviei anteriormente)"
fi

echo "[obs] subindo Prometheus e Grafana…"
docker compose up -d prometheus grafana

echo "[obs] aguardando logs do Grafana (Ctrl+C para sair)…"
docker compose logs -f grafana
