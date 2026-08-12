"""Pydantic v2 models for OmniMind Archive."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class MessageMetadata(BaseModel):
    model_name: Optional[str] = None
    tokens_used: Optional[int] = None
    tags: Optional[list[str]] = None
    source_url: Optional[str] = None
    export_file: Optional[str] = None
    ingested_at: str
    sha256: str
    chunk_index: Optional[int] = None
    chunk_count: Optional[int] = None
    total_tokens: Optional[int] = None
    parent_message_id: Optional[str] = None


class NormalizedMessage(BaseModel):
    schema_version: str = Field(default="1.0")
    message_id: str
    session_id: Optional[str] = None
    source_platform: str = Field(pattern="^(chatgpt|gemini|deepseek|arena)$")
    platform_message_id: Optional[str] = None
    timestamp: str
    role: str = Field(pattern="^(user|assistant|system|other)$")
    content: str = Field(min_length=1)
    tokens: Optional[int] = None
    metadata: MessageMetadata

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("timestamp must end with Z (UTC)")
        datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v

    def to_vector_text(self) -> str:
        return f"[{self.role.upper()}] {self.content}"


class IngestResponse(BaseModel):
    ingest_id: str
    status: str = "queued"
    filename: str
    estimated_wait_seconds: int = 60


class SearchResult(BaseModel):
    message_id: str
    chunk_index: Optional[int] = None
    content: str
    role: str
    timestamp: str
    source_platform: str
    export_file: str
    relevance_score: float
    retrieval_method: str
    pii_redacted: bool = False
    pii_fields_redacted: list[str] = Field(default_factory=list)
    combined_score: Optional[float] = None


class SearchResponse(BaseModel):
    search_id: str
    query: str
    results: list[SearchResult]
    bm25_hits: int
    vector_hits: int
    vector_status: str
    total_latency_ms: float = 0.0
    bm25_latency_ms: float = 0.0
    vector_latency_ms: Optional[float] = None


class RAGQuery(BaseModel):
    q: str = Field(min_length=1)
    redact_level: str = Field(default="min", pattern="^(none|min|max)$")


class RAGResponse(BaseModel):
    query: str
    answer: str
    sources: list[SearchResult]
    synthesis_model: str = "template"
    warning: Optional[str] = None
    pii_warning: Optional[str] = None


class ConsentRecord(BaseModel):
    user_id: str
    timestamp: str
    source_platform: str
    tos_url: str
    tos_version: str
    consent_given: bool
    consent_details: dict[str, Any]
    export_filename: Optional[str] = None
    export_sha256: Optional[str] = None
