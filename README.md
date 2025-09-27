# Video Management Service (FIAP SOAT)

Microsserviço responsável por **gerenciar o ciclo de vida de vídeos**: upload, consulta de status e geração do link de download do arquivo **processado**.

> **Autenticação fora deste serviço**  
> A autenticação/JWT é responsabilidade de um **Auth Service** separado.  
> Aqui apenas **validamos** o token recebido para garantir acesso aos recursos do próprio usuário.

---

## Status e Qualidade do Código

### CI/CD
[![Build](https://github.com/FIAP-Tech-Challenge-SOAT-10/video-upload-service-hackaton/actions/workflows/sonar.yml/badge.svg)](https://github.com/FIAP-Tech-Challenge-SOAT-10/video-upload-service-hackaton/actions/workflows/sonar.yml)

### SonarCloud
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=coverage)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=bugs)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)
[![Vulnerabilities](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=vulnerabilities)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=code_smells)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)
[![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)
[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=FIAP-Tech-Challenge-SOAT-10_video-upload-service-hackaton)

---

## Sumário

- [Arquitetura](#arquitetura)
- [Endpoints](#endpoints)
- [Modelo de Dados](#modelo-de-dados)
- [Como rodar (local / Docker)](#como-rodar-local--docker)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Observabilidade](#observabilidade)
- [Qualidade (Testes, Cobertura e Sonar)](#qualidade-testes-cobertura-e-sonar)
- [Segurança (S3 ExpectedBucketOwner)](#segurança-s3-expectedbucketowner)
- [Roadmap](#roadmap)
- [Licença](#licença)

---

## Arquitetura

### Componentes (MVP)

- **Video Management Service (este repo / FastAPI)**
  - `POST /videos/upload` → faz upload para S3 e publica mensagem na fila
  - `GET /videos/{id_video}` → consulta status (DynamoDB)
  - `GET /videos/download/{video_id}` → gera link **pré-assinado** do ZIP processado
  - `GET /health` → verificação de saúde
  - `GET /metrics` → métricas Prometheus
  - **S3**: armazena o vídeo original (upload) e o `.zip` final  
  - **DynamoDB**: guarda metadados e status  
  - **SQS**: fila para o serviço de processamento

- **Auth Service (externo)**: login/registro/JWT (este serviço **valida** o token)

- **Video Processing Service (externo)**: consome SQS, processa com `ffmpeg`, grava `.zip` no S3 e atualiza status no DynamoDB.

### Diagrama

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
