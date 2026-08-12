from app.retriever import RRFRetriever


def test_fusion_prefers_overlap():
    bm25 = [
        {"message_id": "a", "chunk_index": 0, "content": "alpha"},
        {"message_id": "b", "chunk_index": 0, "content": "beta"},
    ]
    vec = [
        {"message_id": "b", "chunk_index": 0, "content": "beta"},
        {"message_id": "c", "chunk_index": 0, "content": "gamma"},
    ]
    fused = RRFRetriever(final_top_k=3).fuse_results(bm25, vec)
    assert fused[0]["message_id"] == "b"
    assert fused[0]["retrieval_method"] == "fusion"
