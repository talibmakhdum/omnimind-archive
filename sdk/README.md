# OmniMind Python SDK (skeleton)

Minimal REST wrapper around the public FastAPI routes. No new endpoints.

```python
from omnimind import OmniMindClient

with OmniMindClient("http://127.0.0.1:8000", api_key="...") as client:
    print(client.health())
    client.ingest("samples/chatgpt_sample.json")
    print(client.search("machine learning", k=5))
    print(client.query("what is AI?"))
```

Install from this repo (editable):

```bash
pip install -e sdk
```

Or copy `sdk/omnimind/client.py` into your project. See `docs/sdk.md`.
