"""Token-aware chunking with char fallback."""

from __future__ import annotations

import hashlib
from typing import Any


class SimpleTokenizer:
    """Whitespace tokenizer used when HF/tiktoken is unavailable."""

    def encode(self, text: str) -> list[str]:
        return text.split()

    def decode(self, tokens: list[str]) -> str:
        return " ".join(tokens)


class ChunkingEngine:
    def __init__(
        self,
        tokenizer=None,
        chunk_size_tokens: int = 512,
        overlap_pct: float = 0.10,
        fallback_chunk_chars: int = 2048,
    ):
        self.tokenizer = tokenizer or SimpleTokenizer()
        self.chunk_size_tokens = chunk_size_tokens
        self.overlap_tokens = max(1, int(chunk_size_tokens * overlap_pct))
        self.stride_tokens = chunk_size_tokens - self.overlap_tokens
        self.fallback_chunk_chars = fallback_chunk_chars

    def count_tokens(self, text: str) -> int:
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            return max(1, len(text) // 4)

    def chunk_message(
        self,
        content: str,
        message_id: str,
        role: str,
        timestamp: str,
        source_platform: str,
        export_file: str,
        parent_metadata: dict | None = None,
    ) -> list[dict[str, Any]]:
        if not content or len(content.strip()) < 5:
            return []

        parent_metadata = parent_metadata or {}
        total_tokens = self.count_tokens(content)

        if total_tokens <= self.chunk_size_tokens:
            return [
                {
                    "message_id": message_id,
                    "chunk_index": 0,
                    "chunk_count": 1,
                    "content": content,
                    "chunk_tokens": total_tokens,
                    "chunk_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "role": role,
                    "timestamp": timestamp,
                    "source_platform": source_platform,
                    "export_file": export_file,
                    "parent_metadata": parent_metadata,
                }
            ]

        try:
            tokens = self.tokenizer.encode(content)
        except Exception:
            return self._chunk_by_chars(
                content, message_id, role, timestamp, source_platform, export_file, parent_metadata
            )

        chunks: list[dict[str, Any]] = []
        chunk_index = 0
        offset = 0
        while offset < len(tokens):
            end_offset = min(offset + self.chunk_size_tokens, len(tokens))
            chunk_tokens = tokens[offset:end_offset]
            try:
                chunk_text = self.tokenizer.decode(chunk_tokens)
            except Exception:
                chunk_text = " ".join(str(t) for t in chunk_tokens)
            chunk_text = chunk_text.strip()
            if chunk_text:
                chunks.append(
                    {
                        "message_id": message_id,
                        "chunk_index": chunk_index,
                        "chunk_count": -1,
                        "content": chunk_text,
                        "chunk_tokens": len(chunk_tokens),
                        "chunk_sha256": hashlib.sha256(chunk_text.encode()).hexdigest(),
                        "role": role,
                        "timestamp": timestamp,
                        "source_platform": source_platform,
                        "export_file": export_file,
                        "parent_metadata": parent_metadata,
                    }
                )
                chunk_index += 1
            offset += self.stride_tokens

        for chunk in chunks:
            chunk["chunk_count"] = len(chunks)
        return chunks

    def _chunk_by_chars(
        self,
        content: str,
        message_id: str,
        role: str,
        timestamp: str,
        source_platform: str,
        export_file: str,
        parent_metadata: dict,
    ) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        chunk_size_chars = self.fallback_chunk_chars
        overlap_chars = max(1, int(chunk_size_chars * 0.10))
        stride_chars = chunk_size_chars - overlap_chars
        chunk_index = 0
        offset = 0
        while offset < len(content):
            end_offset = min(offset + chunk_size_chars, len(content))
            chunk_text = content[offset:end_offset].strip()
            if chunk_text:
                chunks.append(
                    {
                        "message_id": message_id,
                        "chunk_index": chunk_index,
                        "chunk_count": -1,
                        "content": chunk_text,
                        "chunk_tokens": self.count_tokens(chunk_text),
                        "chunk_sha256": hashlib.sha256(chunk_text.encode()).hexdigest(),
                        "role": role,
                        "timestamp": timestamp,
                        "source_platform": source_platform,
                        "export_file": export_file,
                        "parent_metadata": parent_metadata,
                    }
                )
                chunk_index += 1
            offset += stride_chars
        for chunk in chunks:
            chunk["chunk_count"] = len(chunks)
        return chunks
