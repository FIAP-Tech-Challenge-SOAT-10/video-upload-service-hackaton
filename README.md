# Video Management Service (FIAP SOAT)

Microsserviço responsável por **gerenciar o ciclo de vida dos vídeos**: upload, status e geração de links de download.  

👉 **Não implementa autenticação diretamente.**  
A autenticação e emissão de tokens JWT são tratadas por um **Auth Service** independente.  
Este serviço apenas **valida tokens recebidos** para garantir que cada usuário acesse apenas seus próprios vídeos.  

---

## Arquitetura

### Componentes

- **Video Management Service (este repositório)**  
  - API FastAPI:  
    - `POST /videos/upload` → upload para S3 e envio de mensagem para fila  
    - `GET /videos` → listagem de status por usuário  
    - `GET /videos/{id}` → detalhe de status e link de download (quando disponível)  
  - DynamoDB: persistência de metadados e status  
  - S3: armazenamento do vídeo original e do zip (após processamento)  
  - SQS (ou equivalente): fila para comunicação assíncrona com o serviço de processamento  
  - Observabilidade: logs estruturados + métricas Prometheus  

- **Auth Service (outro microsserviço)**  
  - Cadastro e login de usuários  
  - Emissão de tokens JWT  
  - Este serviço de vídeos apenas **valida tokens** emitidos pelo Auth Service  

- **Video Processing Service (outro microsserviço)**  
  - Worker/consumer da fila  
  - Processa vídeo com `ffmpeg`, gera `.zip` e envia para o S3  
  - Atualiza status no DynamoDB  
  - Notifica erros (via log/webhook/email)

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
