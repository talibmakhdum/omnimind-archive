"""Ingest job queue: RQ+Redis in production, in-memory for CI/dev."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class MemoryJob:
    func: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    result: Any = None
    error: str | None = None
    done: bool = False


class MemoryJobQueue:
    """In-process queue used by tests and local-dev without Redis."""

    def __init__(self, auto_run: bool = False) -> None:
        self.pending: list[MemoryJob] = []
        self.auto_run = auto_run

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> MemoryJob:
        job = MemoryJob(func=func, args=args, kwargs=kwargs)
        self.pending.append(job)
        if self.auto_run:
            self.work_once()
        return job

    def work_once(self) -> MemoryJob | None:
        if not self.pending:
            return None
        job = self.pending.pop(0)
        try:
            job.result = job.func(*job.args, **job.kwargs)
        except Exception as exc:
            job.error = str(exc)
            logger.exception("Memory job failed")
        job.done = True
        return job

    def drain(self) -> None:
        while self.pending:
            self.work_once()


class RQJobQueue:
    def __init__(self, redis_url: str, queue_name: str) -> None:
        import redis
        from rq import Queue

        self.redis = redis.Redis.from_url(redis_url)
        self.queue = Queue(queue_name, connection=self.redis)

    def enqueue(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return self.queue.enqueue(func, *args, **kwargs)


_memory_queue = MemoryJobQueue(auto_run=False)


def get_memory_queue() -> MemoryJobQueue:
    return _memory_queue


def enqueue_ingest(ingest_id: str, file_path: str, filename: str, source_platform: str) -> Any:
    """Enqueue run_ingest_job. Uses RQ when QUEUE_BACKEND=rq, else memory."""
    from app.ingest import run_ingest_job

    settings = get_settings()
    if settings.queue_backend == "rq" and settings.redis_url:
        try:
            return RQJobQueue(settings.redis_url, settings.queue_name).enqueue(
                run_ingest_job, ingest_id, file_path, filename, source_platform
            )
        except Exception:
            logger.exception("RQ enqueue failed; falling back to in-process job")
    queue = get_memory_queue()
    queue.auto_run = True
    return queue.enqueue(run_ingest_job, ingest_id, file_path, filename, source_platform)
