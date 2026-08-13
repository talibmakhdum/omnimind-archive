"""Prometheus metrics (no-op if client missing)."""

from __future__ import annotations

from typing import Any

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        start_http_server,
    )

    ingest_total = Counter(
        "omnimind_ingest_total", "Total messages ingested", ["source_platform", "status"]
    )
    vectors_indexed_total = Counter("omnimind_vectors_indexed_total", "Total embeddings indexed")
    search_queries_total = Counter("omnimind_search_queries_total", "Total search queries", ["method"])
    search_latency_seconds = Histogram(
        "omnimind_search_latency_seconds",
        "Search latency",
        ["method"],
        buckets=(0.1, 0.5, 1.0, 5.0, 10.0),
    )
    vectors_in_db = Gauge("omnimind_vectors_in_db_total", "Total vectors in database")
    REQUESTS = Counter(
        "omnimind_requests_total",
        "Total HTTP requests",
        ["path", "method", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "omnimind_request_latency_seconds",
        "Request latency seconds",
        ["path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
    QUEUE_LENGTH = Gauge("omnimind_queue_length", "Ingest queue depth")
    VECTOR_STORE_HEALTH = Gauge(
        "omnimind_vector_store_health",
        "Vector store health (1=ok, 0.5=memory fallback, 0=error)",
    )
    HTTP_ERRORS = Counter(
        "omnimind_http_errors_total",
        "HTTP 4xx/5xx responses",
        ["path", "status"],
    )
    PURGE_DELETED = Counter(
        "omnimind_purge_deleted_total",
        "Documents deleted by retention purge",
        ["entity"],
    )
except Exception:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    class _N:
        def labels(self, *a: Any, **k: Any) -> "_N":
            return self

        def inc(self, *a: Any, **k: Any) -> None:
            pass

        def observe(self, *a: Any, **k: Any) -> None:
            pass

        def set(self, *a: Any, **k: Any) -> None:
            pass

    ingest_total = _N()  # type: ignore[assignment]
    vectors_indexed_total = _N()  # type: ignore[assignment]
    search_queries_total = _N()  # type: ignore[assignment]
    search_latency_seconds = _N()  # type: ignore[assignment]
    vectors_in_db = _N()  # type: ignore[assignment]
    REQUESTS = _N()  # type: ignore[assignment]
    REQUEST_LATENCY = _N()  # type: ignore[assignment]
    QUEUE_LENGTH = _N()  # type: ignore[assignment]
    VECTOR_STORE_HEALTH = _N()  # type: ignore[assignment]
    HTTP_ERRORS = _N()  # type: ignore[assignment]
    PURGE_DELETED = _N()  # type: ignore[assignment]

    def generate_latest(*_a: Any, **_k: Any) -> bytes:  # type: ignore[misc]
        return b"# omnimind metrics unavailable\n"

    def start_http_server(port: int = 8000, *args: Any, **kwargs: Any) -> None:  # type: ignore[misc]
        return None


def metrics_response_body() -> bytes:
    try:
        from app.jobs import queue_length

        QUEUE_LENGTH.set(queue_length())
    except Exception:
        pass
    return generate_latest()


def start_metrics_server(port: int = 8000) -> None:
    start_http_server(port)


def set_vector_health(status: str) -> None:
    mapping = {"ok": 1.0, "memory": 0.5, "degraded": 0.5, "error": 0.0}
    VECTOR_STORE_HEALTH.set(mapping.get(status, 0.0))


def observe_request(path: str, method: str, status: int, latency_seconds: float) -> None:
    REQUESTS.labels(path=path, method=method, status=str(status)).inc()
    REQUEST_LATENCY.labels(path=path).observe(latency_seconds)
    if status >= 400:
        HTTP_ERRORS.labels(path=path, status=str(status)).inc()
