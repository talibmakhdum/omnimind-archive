import sqlite3

import pytest

from app.db import init_db
from app.embedder import EmbeddingEngine, InMemoryVectorDB
from app.ingest import ChatGPTIngestPipeline
from app.search import SearchService


@pytest.fixture
def sample_chatgpt_export():
    return {
        "conversations": [
            {
                "id": "conv_1",
                "title": "ML Basics",
                "create_time": 1705312800,
                "messages": [
                    {
                        "id": "msg_1",
                        "role": "user",
                        "content": {"content_type": "text", "parts": ["What is machine learning?"]},
                        "create_time": 1705312800,
                    },
                    {
                        "id": "msg_2",
                        "role": "assistant",
                        "content": {
                            "content_type": "text",
                            "parts": [
                                "Machine learning is a subset of AI that learns patterns from data using algorithms."
                            ],
                        },
                        "create_time": 1705312900,
                    },
                    {
                        "id": "msg_3",
                        "role": "user",
                        "content": {"content_type": "text", "parts": ["What is artificial intelligence?"]},
                        "create_time": 1705313000,
                    },
                    {
                        "id": "msg_4",
                        "role": "assistant",
                        "content": {
                            "content_type": "text",
                            "parts": ["Artificial intelligence is the science of making machines perform cognitive tasks."],
                        },
                        "create_time": 1705313100,
                    },
                ],
            }
        ]
    }


def _pipeline(tmp_path):
    conn = init_db(sqlite3.connect(str(tmp_path / "test.db")))
    embedder = EmbeddingEngine(allow_fallback=True)
    embedder.model = None
    vec = type("V", (), {})()
    mem = InMemoryVectorDB()
    vec.add_embeddings = mem.add_embeddings
    vec.query = mem.query
    pipe = ChatGPTIngestPipeline(conn, embedder=embedder, vector_db=vec, force_ingest=False)
    return conn, pipe, embedder, vec


def test_ingest_e2e(tmp_path, sample_chatgpt_export):
    conn, pipeline, _, _ = _pipeline(tmp_path)
    result = pipeline.ingest(sample_chatgpt_export, "test.json", "chatgpt")
    assert result["total_messages"] == 4
    assert result["total_chunks"] >= 4
    assert result["failed_messages"] == []
    assert result["status"] == "completed"


def test_ingest_with_duplicates(tmp_path, sample_chatgpt_export):
    _, pipeline, _, _ = _pipeline(tmp_path)
    result1 = pipeline.ingest(sample_chatgpt_export, "test.json", "chatgpt")
    result2 = pipeline.ingest(sample_chatgpt_export, "test.json", "chatgpt")
    assert result1["total_messages"] == 4
    assert result2["total_messages"] == 0


def test_search_and_rag(tmp_path, sample_chatgpt_export):
    conn, pipeline, embedder, vec = _pipeline(tmp_path)
    pipeline.ingest(sample_chatgpt_export, "test.json", "chatgpt")
    svc = SearchService(conn, embedder=embedder, vector_db=vec)
    out = svc.hybrid("machine learning", k=5, redact_level="min")
    assert out["results"]
    assert any("machine" in r["content"].lower() for r in out["results"])
    rag = svc.rag("what is AI", "min")
    assert rag["answer"]
    assert rag["sources"]
    assert "let me think step by step" not in rag["answer"].lower()
    for source in rag["sources"]:
        assert source["message_id"]
        assert source["timestamp"]
        assert source["source_platform"]
        assert source["export_file"]
