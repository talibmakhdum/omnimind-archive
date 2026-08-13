from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from app.db import get_connection, init_db, wal_mode
from app.embedder import EmbeddingEngine, InMemoryVectorDB
from app.ingest import ChatGPTIngestPipeline
from app.search import SearchService

SAMPLE = {
    "conversations": [
        {
            "id": "conv_c",
            "create_time": 1705312800,
            "messages": [
                {
                    "id": f"msg_{i}",
                    "role": "user",
                    "content": {"content_type": "text", "parts": [f"Concurrent machine learning note {i}"]},
                    "create_time": 1705312800 + i,
                }
                for i in range(8)
            ],
        }
    ]
}


def test_wal_mode_enabled(tmp_path):
    init_db(db_path=str(tmp_path / "wal.db"))
    assert wal_mode(str(tmp_path / "wal.db")).lower() == "wal"


@pytest.mark.asyncio
async def test_concurrent_ingest_and_search(tmp_path):
    db_path = str(tmp_path / "conc.db")
    init_db(db_path=db_path)
    errors: list[BaseException] = []

    def ingest_once(n: int) -> None:
        try:
            with get_connection(db_path) as conn:
                emb = EmbeddingEngine(allow_fallback=True)
                emb.model = None
                mem = InMemoryVectorDB()
                pipe = ChatGPTIngestPipeline(conn, embedder=emb, vector_db=mem, force_ingest=True)
                pipe.ingest(SAMPLE, f"export-{n}.json", "chatgpt")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def search_once() -> None:
        try:
            with get_connection(db_path) as conn:
                emb = EmbeddingEngine(allow_fallback=True)
                emb.model = None
                SearchService(conn, embedder=emb, vector_db=InMemoryVectorDB()).hybrid("machine", k=3)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(ingest_once, i) for i in range(3)]
        futs += [pool.submit(search_once) for _ in range(6)]
        for f in as_completed(futs):
            f.result()

    assert not any(isinstance(e, sqlite3.OperationalError) for e in errors), errors
    assert errors == []
