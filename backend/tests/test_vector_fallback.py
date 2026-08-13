import sys
import types

import pytest
from app.embedder import ChromaVectorDB


def test_inmemory_allowed_when_chroma_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "chromadb", None)
    # If chromadb is already imported, force the except path via a dummy module that fails
    fake = types.ModuleType("chromadb")

    def _fail(*_a, **_k):
        raise RuntimeError("no persist")

    fake.PersistentClient = _fail  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "chromadb", fake)
    db = ChromaVectorDB(persist_dir="/tmp/none-chroma", allow_inmemory=True)
    assert db.backend == "memory"
    assert db.health() == "ok"


def test_inmemory_forbidden_raises(monkeypatch):
    fake = types.ModuleType("chromadb")

    def _fail(*_a, **_k):
        raise RuntimeError("no persist")

    fake.PersistentClient = _fail  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "chromadb", fake)
    with pytest.raises(RuntimeError, match="ALLOW_INMEMORY_VECTORS"):
        ChromaVectorDB(persist_dir="/tmp/none-chroma", allow_inmemory=False)
