"""Structured JSONL audit logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def audit_log(event: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.enable_structured_logging:
        return
    path = Path(settings.audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": now_iso(), **event}
    if settings.log_redact_secrets:
        for key in list(payload):
            if any(s in key.lower() for s in ("key", "secret", "token", "password")):
                payload[key] = "[REDACTED]"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
