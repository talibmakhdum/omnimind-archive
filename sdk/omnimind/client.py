"""Synchronous REST client for OmniMind Archive.

Public HTTP routes are unchanged: /health, /ingest, /search, /query, /admin/*.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class OmniMindError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OmniMindClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: str = "",
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._owns = client is None
        self._http = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        if self._owns:
            self._http.close()

    def __enter__(self) -> "OmniMindClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def _url(self, path: str) -> str:
        if getattr(self._http, "base_url", None):
            return path
        return f"{self.base_url}{path}"

    def _check(self, response: httpx.Response) -> Any:
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise OmniMindError(str(detail), status_code=response.status_code)
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return response.text

    def health(self) -> dict[str, Any]:
        return self._check(self._http.get(self._url("/health")))

    def ingest(
        self,
        file: str | Path | bytes,
        filename: str = "export.json",
        source_platform: str = "chatgpt",
        consent_given: bool = True,
    ) -> dict[str, Any]:
        if isinstance(file, (str, Path)):
            path = Path(file)
            data = path.read_bytes()
            filename = path.name or filename
        else:
            data = file
        files = {"file": (filename, data, "application/json")}
        form = {
            "source_platform": source_platform,
            "consent_given": "true" if consent_given else "false",
        }
        return self._check(self._http.post(self._url("/ingest"), files=files, data=form, headers=self._headers()))

    def search(self, q: str, k: int = 10, redact_level: str = "min") -> dict[str, Any]:
        return self._check(
            self._http.get(
                self._url("/search"),
                params={"q": q, "k": k, "redact_level": redact_level},
            )
        )

    def query(self, q: str, redact_level: str = "min") -> dict[str, Any]:
        return self._check(
            self._http.post(
                self._url("/query"),
                json={"q": q, "redact_level": redact_level},
                headers=self._headers(),
            )
        )

    def admin_stats(self) -> dict[str, Any]:
        return self._check(self._http.get(self._url("/admin/stats"), headers=self._headers()))

    def ingest_status(self, ingest_id: str) -> dict[str, Any]:
        return self._check(self._http.get(self._url(f"/ingest/{ingest_id}/status")))
