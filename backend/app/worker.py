"""RQ worker entrypoint: python -m app.worker"""

from __future__ import annotations

import sys

from app.config import ensure_dirs, get_settings
from app.db import init_db
from app.logging_setup import configure_logging, init_sentry


def main() -> int:
    configure_logging()
    init_sentry()
    settings = get_settings()
    ensure_dirs(settings)
    init_db()
    if not settings.redis_url:
        print("REDIS_URL is required for the RQ worker", file=sys.stderr)
        return 2
    import redis
    from rq import Queue, Worker

    conn = redis.Redis.from_url(settings.redis_url)
    queues = [Queue(settings.queue_name, connection=conn)]
    Worker(queues, connection=conn).work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
