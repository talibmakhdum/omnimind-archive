# SDK, REST client, and multi-user sessions

## Python client

Package: `sdk/omnimind` (install with `pip install -e sdk`).

```python
from omnimind import OmniMindClient

client = OmniMindClient(base_url="http://127.0.0.1:8000", api_key="omk_...")
client.health()
client.ingest("samples/chatgpt_sample.json", source_platform="chatgpt")
client.search("machine learning", k=10, redact_level="min")
client.query("what is AI?")
client.admin_stats()
client.close()
```

The client is a thin httpx wrapper around the public routes. It does not add APIs.

## REST examples

```bash
curl -s localhost:8000/health
curl -s -H "Authorization: Bearer $API_KEY" localhost:8000/admin/stats
curl -s "localhost:8000/search?q=machine+learning&k=5"
curl -s -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"q":"what is AI?","redact_level":"min"}' \
  localhost:8000/query
```

## Multi-user session guidance

The core archive is **single-tenant by default** (one SQLite file, one Chroma collection).

### Streamlit (today)

- `st.session_state` is per browser session: `ingest_id` / `search_id` do not leak across users in the same process.
- The UI still shares one `API_KEY` and one backend. Every user sees the same corpus.
- Always set `API_KEY` in the Streamlit environment so ingest and `/query` succeed when auth is on.

### Recommended multi-user shape

1. **Issue per-user API keys** (`POST /admin/api-keys`) and map `name` → user id.
2. Stamp `consent_records.user_id` and `messages.session_id` with that id at ingest (extend the pipeline; do not reuse another user’s export).
3. Filter search by `session_id` / `user_id` before returning hits (future query param — not added yet to keep the public API stable).
4. Run Streamlit with `server.enableXsrfProtection=true` and put it behind the same origin allow-list (`ALLOWED_ORIGINS`).
5. For true isolation, give each tenant a `DATA_DIR` / collection name (separate process or schema).

### Horizontal sessions

Put a shared Redis behind RQ + the rate limiter (`REDIS_URL`) so API replicas share queue and limit state. Sticky sessions are not required for the API; Streamlit session state is local to each UI replica — use a shared session backend if you scale Streamlit.
