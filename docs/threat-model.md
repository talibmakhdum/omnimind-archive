# Threat model (short)

## Sensitive assets

| Asset | Location | Control |
|---|---|---|
| Chat archives | SQLite `messages` / `chunks` | Disk permissions, optional encryption at rest (OS/LUKS) |
| Embeddings | Chroma persist dir | Same volume policy as SQLite |
| API keys | `api_keys.key_hash`, env | bcrypt; never log; redact `*key*` / `*token*` |
| Uploads | `UPLOAD_DIR` | MIME + size validation |
| Consent / audit | `consent_records`, `audit.jsonl` | Append-only; IP truncated |
| Failed exports | `FAILED_EXPORTS_DIR` | Same retention as uploads |

## Actors

- Local operator (trusted)
- UI user with a bearer token
- Anonymous client (search + probes only)
- Malicious uploader (zip bombs, polyglots, huge files)
- Adjacent process on the host

## Expected controls

- Auth on mutate/admin routes; hashed storage.
- Rate limits (Redis-backed when scaled out).
- CORS allow-list (no `*`).
- Upload sniffing + cap.
- PII redaction on read.
- Dependabot + `pip-audit` in CI; GitHub secret scanning on the repo.
- No remote LLM unless explicitly enabled later.

## Out of scope (today)

- Multi-tenant row-level security (see `docs/sdk.md`)
- CSRF on cookie sessions (API is bearer-only)
- Full disk encryption (delegate to the host)
