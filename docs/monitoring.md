# Monitoring

## Prometheus

Scrape the API:

```yaml
scrape_configs:
  - job_name: omnimind
    metrics_path: /metrics
    static_configs:
      - targets: ["fastapi:8000"]
```

Optional sidecar (if you prefer a dedicated port):

```python
from app.metrics import start_metrics_server
start_metrics_server(9090)
```

### Metrics

| Name | Type | Meaning |
|---|---|---|
| `omnimind_requests_total` | Counter | HTTP requests by path/method/status |
| `omnimind_request_latency_seconds` | Histogram | Request latency |
| `omnimind_http_errors_total` | Counter | 4xx/5xx |
| `omnimind_queue_length` | Gauge | Ingest queue depth |
| `omnimind_vector_store_health` | Gauge | 1=Chroma ok, 0.5=memory fallback, 0=error |
| `omnimind_vectors_in_db_total` | Gauge | Indexed vectors |
| `omnimind_ingest_total` | Counter | Messages ingested |
| `omnimind_vectors_indexed_total` | Counter | Embeddings written |
| `omnimind_search_queries_total` | Counter | Search calls |
| `omnimind_search_latency_seconds` | Histogram | Retriever latency |
| `omnimind_purge_deleted_total` | Counter | Retention deletions |

Dashboard JSON: `docs/grafana/dashboard.json`  
Alert rules: `docs/grafana/alerts.yml`

## Import Grafana dashboard

1. Create a Prometheus datasource named `Prometheus` (uid `prometheus` works with the template).
2. Dashboards → Import → upload `docs/grafana/dashboard.json`.

## Alerting (minimum)

- High error rate (`5xx` ratio)
- High p95 latency
- Vector store health = 0
- Queue length stuck high
- Backup job failure (external; alert on cron/`systemd` unit)

Wire `docs/grafana/alerts.yml` as a Prometheus rule file or Grafana-managed alert.

## Sentry

Set `SENTRY_DSN` to capture unhandled exceptions (5% traces).
