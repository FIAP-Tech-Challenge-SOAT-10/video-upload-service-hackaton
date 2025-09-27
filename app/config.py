# app/config.py
from typing import Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Defaults "normais" (sobrepostos por env/.env)
    aws_region: str = "us-east-1"
    aws_endpoint_url: Optional[str] = None
    s3_bucket: str = "video-service-bucket"
    ddb_table: str = "videos"
    sqs_queue_url: str = ""
    max_upload_mb: int = 200

    # Vars do Auth (obrigatório: auth_base_url)
    # Mapear tanto MAIÚSCULA (env) quanto snake_case se quiser
    auth_base_url: str = Field(
        ...,
        validation_alias=AliasChoices("AUTH_BASE_URL", "auth_base_url"),
    )
    auth_timeout_seconds: int = Field(
        5,
        validation_alias=AliasChoices("AUTH_TIMEOUT_SECONDS", "auth_timeout_seconds"),
    )
    auth_cache_ttl_seconds: int = Field(
        30,
        validation_alias=AliasChoices("AUTH_CACHE_TTL_SECONDS", "auth_cache_ttl_seconds"),
    )

    # pydantic-settings v2
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",   # sem prefixo
        extra="ignore",
    )

settings = Settings()
