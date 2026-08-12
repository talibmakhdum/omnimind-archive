from app.chunker import ChunkingEngine


def test_skip_tiny():
    engine = ChunkingEngine(chunk_size_tokens=8)
    assert engine.chunk_message("hi", "m", "user", "2024-01-15T10:00:00Z", "chatgpt", "f.json") == []


def test_single_chunk():
    engine = ChunkingEngine(chunk_size_tokens=64)
    chunks = engine.chunk_message(
        "What is machine learning in one sentence please?",
        "m1",
        "user",
        "2024-01-15T10:00:00Z",
        "chatgpt",
        "f.json",
    )
    assert len(chunks) == 1
    assert chunks[0]["chunk_count"] == 1


def test_multi_chunk():
    engine = ChunkingEngine(chunk_size_tokens=8, overlap_pct=0.25)
    words = " ".join(f"token{i}" for i in range(40))
    chunks = engine.chunk_message(words, "m2", "assistant", "2024-01-15T10:00:00Z", "chatgpt", "f.json")
    assert len(chunks) > 1
    assert all(c["chunk_count"] == len(chunks) for c in chunks)
