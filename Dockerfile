# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# --- Carimbo de commit (passado via build-arg) ---
ARG GIT_SHA=dev
LABEL org.opencontainers.image.revision=$GIT_SHA
RUN echo "$GIT_SHA" > /app/REVISION

# Dependências de sistema úteis (SSL/DNS/etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl netbase \
 && rm -rf /var/lib/apt/lists/*

# Primeiro requirements para cache mais eficiente
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copia o código
COPY app /app/app

# Usuário não-root
RUN useradd -m -u 10001 appuser
USER appuser

EXPOSE 8094

# Substitua "app.main:app" se seu módulo/variável forem diferentes
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8094"]
