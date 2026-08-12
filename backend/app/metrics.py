"""Prometheus metrics (no-op if client missing)."""

from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram, Gauge

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
except Exception:  # pragma: no cover
    class _N:
        def labels(self, *a, **k):
            return self

        def inc(self, *a, **k):
            pass

        def observe(self, *a, **k):
            pass

        def set(self, *a, **k):
            pass

    ingest_total = vectors_indexed_total = search_queries_total = search_latency_seconds = vectors_in_db = _N()
