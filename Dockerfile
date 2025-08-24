# syntax=docker/dockerfile:1
FROM python:3.12-slim

# ====== Configuração base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Diretório de trabalho
WORKDIR /app

# (Opcional, mas recomendado) Dependências do sistema usadas por libs comuns de rede/ssl
# e para certificados / resolução DNS em ambientes corporativos.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl netbase \
 && rm -rf /var/lib/apt/lists/*

# ====== Instalação de dependências Python
# Copiamos apenas o requirements primeiro para aproveitar cache de camadas
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# ====== Copiar a aplicação
# Estrutura esperada:
# /app
#   └── app/
#       └── main.py  (expondo "app = FastAPI()")
COPY app /app/app

# ====== Usuário não-root por segurança
RUN useradd -m -u 10001 appuser
USER appuser

# Porta que a API expõe
EXPOSE 8094

# ====== Comando de execução
# Ajuste "app.main:app" se o módulo/variável diferirem.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8094"]
