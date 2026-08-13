# Architecture

Privacy-first, local-by-default semantic search over chat export archives.

![Architecture](architecture.png)

```mermaid
flowchart LR
  subgraph clients [Clients]
    UI[Streamlit UI]
    SDK[Python SDK]
    HTTP[OpenAPI / curl]
  end

  subgraph api [FastAPI]
    AUTH[bcrypt API keys]
    RL[Rate limiter]
    VAL[Upload validation]
    MW[Prometheus middleware]
  end

  subgraph workers [Async ingest]
    Q[RQ + Redis or in-process queue]
    W[Worker]
  end

  subgraph data [Data plane]
    SQL[(SQLite WAL)]
    FTS[FTS5 BM25]
    EMB[Embeddings local / hash fallback]
    VEC[(Chroma or in-memory)]
  end

  subgraph ops [Ops]
    PROM[/metrics]
    GRAF[Grafana]
    PURGE[Retention purge]
    BAK[Backup scripts]
  end

  UI --> api
  SDK --> api
  HTTP --> api
  AUTH --> SQL
  VAL --> Q
  Q --> W
  W --> SQL
  W --> EMB --> VEC
  W --> FTS
  api --> FTS
  api --> VEC
  api --> PROM --> GRAF
  PURGE --> SQL
  BAK --> SQL
```

## Request paths

| Route | Auth | Notes |
|---|---|---|
| `POST /ingest` | Bearer | MIME + size check, consent required, queued |
| `GET /ingest/{id}/status` | public | Job progress |
| `GET /search` | public | Hybrid BM25 + vector + RRF |
| `POST /query` | Bearer | Template RAG over hybrid hits |
| `GET /admin/*` | Bearer | Stats and hashed API key admin |
| `GET /health` `/live` `/ready` `/metrics` | public | Probes and Prometheus |

## Trust boundaries

- The API process is the only writer to SQLite and the vector directory.
- API keys are bcrypt-hashed in `api_keys` (and the env key is hashed in memory). Plaintext is shown once at creation.
- Uploads are sniffed (`{`, PNG/JPEG/PDF magic) before they touch the parser.
- PII redaction happens on the read path (`none` / `min` / `max`).
- Vector fallback (`ALLOW_INMEMORY_VECTORS`) is for tests/dev only.

## Scaling sketch

| Component | Single node (today) | Horizontal next step |
|---|---|---|
| Metadata | SQLite + WAL | Postgres (`pg_dump` / transform, see `docs/ops.md`) |
| Lexical search | FTS5 | Postgres FTS or OpenSearch |
| Vectors | Local Chroma | Chroma cluster, Milvus, or Pinecone |
| Queue | Memory or one Redis | Shared Redis + N RQ workers |
| API | One uvicorn | Stateless replicas behind a load balancer |

Keep migrations backward compatible so rolling deploys stay online.
