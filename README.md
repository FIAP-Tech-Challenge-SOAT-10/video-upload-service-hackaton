# Video Management Service (FIAP SOAT)

Microsserviço responsável por **gerenciar o ciclo de vida dos vídeos**: upload, status e geração de links de download.

> ❗ **Autenticação fora deste serviço**  
> A autenticação e a emissão de tokens JWT são tratadas por um **Auth Service** independente.  
> Este serviço apenas **valida tokens recebidos** para garantir que cada usuário acesse apenas seus próprios vídeos.

---

## Sonar Quality Gate Status

[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=<SEU_PROJECT_KEY>&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)


## Arquitetura

### Componentes

- **Video Management Service (este repositório)**
  - API FastAPI:
    - `POST /videos/upload` → upload para S3 e envio de mensagem para a fila
    - `GET /videos` → listagem de status por usuário (paginação por cursor)
    - `GET /videos/{id_video}` → detalhe de status do vídeo
    - `GET /videos/download/{video_id}` → link pré-assinado do **ZIP processado**
    - `GET /health` → verificação de saúde
  - DynamoDB: persistência de metadados e status
  - S3: armazenamento do vídeo original e do `.zip` (após processamento)
  - SQS (ou equivalente): mensageria com retries/DLQ
  - Observabilidade: **logs estruturados** + **métricas Prometheus (/metrics)**

- **Auth Service (outro microsserviço)**
  - Cadastro/login de usuários
  - Emissão de tokens JWT (claim `sub` ou `user_id`)
  - Este serviço **valida** tokens emitidos pelo Auth

- **Video Processing Service (outro microsserviço)**
  - Worker/consumer da fila
  - Processa o vídeo com `ffmpeg`, gera `.zip` e envia para S3
  - Atualiza status no DynamoDB (`PROCESSING` → `DONE`/`ERROR`)
  - Notifica erros (log/webhook/email)

---

## Diagrama da Arquitetura

```mermaid
flowchart LR
    User -->|Login| AuthService[Auth Service]
    User -->|Upload vídeo c/ JWT| VideoAPI[Video Management Service]
    VideoAPI -->|Grava metadados| DynamoDB[(DynamoDB)]
    VideoAPI -->|Armazena vídeo| S3[(S3)]
    VideoAPI -->|Envia mensagem| SQS[(SQS)]
    VideoWorker[Video Processing Service] -->|Consome fila| SQS
    VideoWorker -->|Processa frames/zip| S3
    VideoWorker -->|Atualiza status| DynamoDB
    User -->|Consulta status/download| VideoAPI
