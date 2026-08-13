# RAG / LLM configuration

Default synthesis is **extractive/template** (`synthesis_model: "template"`). No tokens leave the machine unless you add a provider.

## Retriever knobs (`.env`)

| Variable | Default | Role |
|---|---|---|
| `EMBEDDING_PROVIDER` | `local` | Only local embeddings are implemented |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Used when `requirements-ml.txt` is installed |
| `EMBEDDING_BATCH_SIZE` | `32` | Ingest batch |
| `VECTOR_DB` | `chroma` | Local persistent store |
| `CHROMA_PERSIST_DIR` | `.chroma` | Durable path |
| `ALLOW_INMEMORY_VECTORS` | `true` | Tests/dev fallback |
| `BM25_TOP_K` / `VECTOR_TOP_K` | `50` | Candidate lists |
| `RRF_K` | `60` | Reciprocal rank fusion |
| `ALPHA_VECTOR` / `ALPHA_BM25` | `1.5` / `1.0` | Fusion weights |
| `FINAL_TOP_K` | `10` | Returned hits |
| `REDACT_LEVEL` | `min` | `none` \| `min` \| `max` |

Hash embeddings kick in automatically when `sentence-transformers` is missing so CI stays offline.

## Adding a real LLM (guidance only)

Keep the public `POST /query` body stable (`q`, `redact_level`). Behind the flag:

1. Retrieve with `SearchService.hybrid` (already redacted).
2. Build a prompt that **only** cites returned `message_id`s.
3. Call a local model (Ollama / llama.cpp) by default; require an explicit `ALLOW_REMOTE_LLM=true` plus a key for cloud providers.
4. Never send raw exports or API keys to the model. Re-run the redactor on the completion.

Document the provider in `synthesis_model` so clients can tell template vs LLM answers apart.

## Vector backends

| Backend | When to use | Config |
|---|---|---|
| In-memory | pytest / laptops without Chroma | `ALLOW_INMEMORY_VECTORS=true` |
| Local Chroma | Single-node production | `pip install -r backend/requirements-ml.txt`, persist dir on a volume |
| Cluster Chroma / Milvus / Pinecone | Horizontal scale | Swap `ChromaVectorDB` for a driver that implements `add_embeddings`, `query`, `health`, `count`, `delete_ids` |

Tests assert the in-memory fallback path (`backend/tests/test_vector_fallback.py`, `test_db_readwrite.py`).
