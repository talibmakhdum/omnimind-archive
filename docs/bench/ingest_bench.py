#!/usr/bin/env python3
"""Lightweight ingest/search latency harness.

Not run on the default CI gate. Use docs/github-actions/benchmark.yml
or: PYTHONPATH=backend python docs/bench/ingest_bench.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
from pathlib import Path

from app.db import init_db
from app.embedder import EmbeddingEngine, InMemoryVectorDB
from app.ingest import ChatGPTIngestPipeline
from app.search import SearchService


def _payload(n: int) -> dict:
    messages = []
    for i in range(n):
        messages.append(
            {
                "id": f"msg_{i}",
                "role": "user" if i % 2 == 0 else "assistant",
                "content": {"content_type": "text", "parts": [f"Benchmark note {i} about machine learning and retrieval."]},
                "create_time": 1705312800 + i,
            }
        )
    return {"conversations": [{"id": "bench", "create_time": 1705312800, "messages": messages}]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", type=int, default=100)
    parser.add_argument("--queries", type=int, default=10)
    parser.add_argument("--out", default="docs/bench/results.json")
    args = parser.parse_args()

    db_path = Path(".data/bench.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = init_db(sqlite3.connect(str(db_path)))
    embedder = EmbeddingEngine(allow_fallback=True)
    embedder.model = None
    vec = InMemoryVectorDB()
    pipe = ChatGPTIngestPipeline(conn, embedder=embedder, vector_db=vec, force_ingest=True)

    t0 = time.perf_counter()
    result = pipe.ingest(_payload(args.docs), "bench.json", "chatgpt")
    ingest_s = time.perf_counter() - t0

    svc = SearchService(conn, embedder=embedder, vector_db=vec)
    latencies = []
    for i in range(args.queries):
        q0 = time.perf_counter()
        svc.hybrid("machine learning", k=10, redact_level="none")
        latencies.append(time.perf_counter() - q0)

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0
    summary = {
        "docs": args.docs,
        "ingested_messages": result.get("total_messages"),
        "ingest_seconds": round(ingest_s, 4),
        "ingest_docs_per_sec": round(args.docs / ingest_s, 2) if ingest_s else 0,
        "queries": args.queries,
        "search_p50_seconds": round(p50, 4),
        "search_p95_seconds": round(p95, 4),
        "vector_backend": "memory",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    csv_path = out.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(summary))
        writer.writeheader()
        writer.writerow(summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
