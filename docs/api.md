# API reference

The live contract is FastAPI’s OpenAPI schema:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Machine-readable: `http://127.0.0.1:8000/openapi.json`

No public route was removed or renamed in 1.2.0. Additive admin routes: `/admin/api-keys`.

## Authentication

Protected routes expect:

```
Authorization: Bearer <api-key>
```

The server stores **bcrypt hashes** only (`api_keys.key_hash`, or `API_KEY_HASH`). `API_KEY` in the environment is hashed in memory at first use and never written to SQLite.

| Route | Auth |
|---|---|
| `GET /health` `GET /live` `GET /ready` `GET /metrics` | No |
| `GET /search` `GET /search/{id}/results` `GET /ingest/{id}/status` | No |
| `POST /ingest` `POST /query` `GET /admin/stats` | Bearer |
| `POST/GET/DELETE /admin/api-keys` | Bearer |

When `AUTH_REQUIRED=false` and both `API_KEY` and `API_KEY_HASH` are empty, protected routes are open (local demo only).

## Ingest

`POST /ingest` `multipart/form-data`

| Field | Notes |
|---|---|
| `file` | JSON chat export. Size ≤ `MAX_UPLOAD_SIZE_MB`. MIME sniffed (`application/json`). |
| `source_platform` | `chatgpt` \| `gemini` \| `deepseek` \| `arena` |
| `consent_given` | must be true |
| `tos_url` / `tos_version` | recorded on `consent_records` |

Responses: `200` queued, `400` bad MIME/JSON, `401` auth, `403` no consent, `413` too large, `429` rate limit.

## Search and RAG

`GET /search?q=&k=10&redact_level=min`

Returns hybrid BM25 + vector results with `search_id`, hit counts, and latencies.

`POST /query`

```json
{"q": "what is AI?", "redact_level": "min"}
```

Template synthesis over the same hybrid retriever (no remote LLM in the default build).

## Admin

`GET /admin/stats` — message count, jobs, vector backend, queue length.

`POST /admin/api-keys` `{"name": "ci-robot"}` — returns `{id, name, api_key}` **once**.

`GET /admin/api-keys` — metadata only (no hashes, no secrets).

`DELETE /admin/api-keys/{id}` — revoke.

## Rate limits

Configurable: `RATE_LIMIT_INGEST_PER_HOUR`, `RATE_LIMIT_SEARCH_PER_MINUTE`, `RATE_LIMIT_QUERY_PER_MINUTE`. Redis sliding window when `REDIS_URL` is set; otherwise in-process.

## Errors

JSON `{"detail": "..."}` with standard HTTP status codes. `429` for the limiter, `503` on `/ready` if SQLite is down.
