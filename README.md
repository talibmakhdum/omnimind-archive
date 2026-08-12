# OmniMind Archive

Privacy-first, fully local-by-default semantic search for chat export archives (ChatGPT MVP; Gemini / DeepSeek / Arena adapters stubbed).

**Core promise**

- Zero cloud data transmission by default (`LOCAL_ONLY=true`)
- Works on 2–4 GB RAM laptops (hash-embedding fallback if the MiniLM model is not downloaded)
- Hybrid BM25 (SQLite FTS5) + vector (Chroma or in-memory) search with RRF fusion
- Full attribution / provenance on every hit
- Explicit consent + JSONL audit log
- Configurable PII redaction (`none` / `min` / `max`)
- Idempotent, resumable ingest with checkpoints

## Quick start

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt -r ui/requirements.txt
cp .env.example .env
python backend/scripts/init_db.py

# Terminal 1
cd backend && PYTHONPATH=. uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd ui && streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

UI: `http://localhost:8501` · API docs: `http://localhost:8000/docs`

Upload `samples/chatgpt_sample.json` (check both consent boxes) then search for `machine learning`.

## Tests

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

## Docker

```bash
docker compose up --build
```

## Architecture (MVP)

```
Streamlit ──POST /ingest──► FastAPI ──► normalize → dedupe → chunk
                                      ──► PII-aware search output
                                      ──► SQLite FTS5 + Chroma/in-memory
GET /search  hybrid BM25 + vector + RRF
POST /query  template RAG with source attribution
```

Phase 2: Gemini / DeepSeek / Arena parsers, optional OpenAI/HF embeddings, Qdrant Cloud.

## Security notes

- Consent is required on `/ingest` (HTTP 403 otherwise) and stored in `consent_records`.
- Audit events append to `.data/audit.jsonl`.
- Secrets in logs are redacted. Do not commit `.env`.
