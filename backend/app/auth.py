"""Bearer API key authentication."""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.config import get_settings


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = (settings.api_key or "").strip()
    required = settings.auth_required or bool(expected)
    if not required:
        return
    if not expected:
        raise HTTPException(status_code=401, detail="API key not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
