"""Chat export parsers. MVP: ChatGPT; stubs for Gemini/DeepSeek/Arena."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator


def _iso_from_unix(ts: float | int | None) -> str:
    if ts is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = content.get("parts") or content.get("text") or []
        if isinstance(parts, str):
            return parts
        if isinstance(parts, list):
            bits: list[str] = []
            for p in parts:
                if isinstance(p, str):
                    bits.append(p)
                elif isinstance(p, dict) and "text" in p:
                    bits.append(str(p["text"]))
            return "\n".join(bits)
    return str(content)


def iter_chatgpt_messages(payload: Any) -> Iterator[dict[str, Any]]:
    """Normalize ChatGPT export JSON (list of conversations or wrapped)."""
    conversations = payload
    if isinstance(payload, dict):
        conversations = (
            payload.get("conversations")
            or payload.get("items")
            or [payload]
        )
    if not isinstance(conversations, list):
        conversations = [conversations]

    for conv in conversations:
        if not isinstance(conv, dict):
            continue
        session_id = str(conv.get("id") or conv.get("conversation_id") or "sess_unknown")
        mapping = conv.get("mapping")
        if isinstance(mapping, dict):
            nodes = list(mapping.values())
            for node in nodes:
                msg = (node or {}).get("message") if isinstance(node, dict) else None
                if not msg:
                    continue
                author = (msg.get("author") or {})
                role = author.get("role") or msg.get("role") or "other"
                if role not in {"user", "assistant", "system", "other"}:
                    role = "other"
                text = _extract_text(msg.get("content"))
                if not text.strip():
                    continue
                yield {
                    "platform_message_id": msg.get("id"),
                    "session_id": session_id,
                    "role": role,
                    "content": text,
                    "timestamp": _iso_from_unix(msg.get("create_time") or conv.get("create_time")),
                    "model_name": (msg.get("metadata") or {}).get("model_slug"),
                }
            continue

        messages = conv.get("messages") or conv.get("chat") or []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role") or (msg.get("author") or {}).get("role") or "other"
            if role not in {"user", "assistant", "system", "other"}:
                role = "other"
            text = _extract_text(msg.get("content") if "content" in msg else msg.get("text"))
            if not text.strip():
                continue
            yield {
                "platform_message_id": msg.get("id"),
                "session_id": session_id,
                "role": role,
                "content": text,
                "timestamp": _iso_from_unix(msg.get("create_time") or conv.get("create_time")),
                "model_name": msg.get("model") or (msg.get("metadata") or {}).get("model_slug"),
            }


def iter_messages(payload: Any, source_platform: str) -> Iterator[dict[str, Any]]:
    # Phase 2 adapters can branch here; ChatGPT-shaped JSON works for all MVP tests.
    return iter_chatgpt_messages(payload)
