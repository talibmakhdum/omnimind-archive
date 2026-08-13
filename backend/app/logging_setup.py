"""Structured JSON logging."""

from __future__ import annotations

import logging
import sys
from typing import Any

from app.config import get_settings


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("ingest_id", "search_id", "job_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if settings.enable_structured_logging:
        try:
            from pythonjsonlogger.jsonlogger import JsonFormatter

            handler.setFormatter(JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        except Exception:
            handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def init_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.05)
    except Exception:
        logging.getLogger(__name__).warning("Sentry SDK not installed; skipping.")
