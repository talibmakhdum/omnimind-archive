"""Application settings loaded from environment / .env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    local_only: bool = True
    force_ingest: bool = False

    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    quantize_level: str = "none"
    quantize_cache_dir: str = ".cache/embeddings"

    vector_db: str = "chroma"
    chroma_persist_dir: str = ".chroma"
    chroma_collection: str = "omnimind_v1"
    allow_inmemory_vectors: bool = True

    bm25_top_k: int = 50
    vector_top_k: int = 50
    rrf_k: int = 60
    alpha_vector: float = 1.5
    alpha_bm25: float = 1.0
    final_top_k: int = 10

    chunk_size_tokens: int = 512
    chunk_overlap_pct: float = 0.10
    fallback_chunk_chars: int = 2048

    redact_level: str = "min"

    data_dir: str = ".data"
    checkpoint_dir: str = ".data/checkpoints"
    failed_exports_dir: str = ".data/failed_exports"
    upload_dir: str = ".data/uploads"
    max_upload_size_mb: int = 500
    retention_days: int = 90
    purge_enabled: bool = False

    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000

    rate_limit_ingest_per_hour: int = 10
    rate_limit_search_per_minute: int = 60
    rate_limit_query_per_minute: int = 20

    enable_metrics: bool = True
    enable_structured_logging: bool = True
    log_redact_secrets: bool = True

    secret_key: str = "dev-secret-key"
    api_key: str = ""
    auth_required: bool = False
    allowed_origins: str = "http://localhost:8501,http://localhost:3000"
    cors_enabled: bool = True

    openai_api_key: str = ""
    huggingface_api_key: str = ""

    redis_url: str = ""
    queue_backend: str = "memory"
    queue_name: str = "omnimind-ingest"

    sentry_dsn: str = ""

    @property
    def db_path(self) -> str:
        return str(Path(self.data_dir) / "archive.db")

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def audit_path(self) -> str:
        return str(Path(self.data_dir) / "audit.jsonl")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def ensure_dirs(settings: Settings | None = None) -> None:
    s = settings or get_settings()
    for d in (
        s.data_dir,
        s.checkpoint_dir,
        s.failed_exports_dir,
        s.upload_dir,
        s.chroma_persist_dir,
        s.quantize_cache_dir,
    ):
        Path(d).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", s.quantize_cache_dir)
