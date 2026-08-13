"""Sliding-window rate limiter (Redis when configured, in-memory otherwise)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings


class RateLimiter:
    def __init__(self, redis_client: Any | None = None) -> None:
        self.redis = redis_client
        self._mem: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.time()
        if self.redis is not None:
            return self._allow_redis(key, limit, window_seconds, now)
        return self._allow_memory(key, limit, window_seconds, now)

    def _allow_memory(self, key: str, limit: int, window_seconds: float, now: float) -> bool:
        with self._lock:
            bucket = [t for t in self._mem[key] if now - t < window_seconds]
            if len(bucket) >= limit:
                self._mem[key] = bucket
                return False
            bucket.append(now)
            self._mem[key] = bucket
            return True

    def _allow_redis(self, key: str, limit: int, window_seconds: float, now: float) -> bool:
        rkey = f"rl:{key}"
        assert self.redis is not None
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(rkey, 0, now - window_seconds)
        pipe.zcard(rkey)
        pipe.zadd(rkey, {f"{now}": now})
        pipe.expire(rkey, int(window_seconds) + 5)
        results = pipe.execute()
        count = int(results[1])
        return count < limit

    def check(self, key: str, limit: int, window_seconds: float) -> None:
        if not self.allow(key, limit, window_seconds):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")


_limiter: RateLimiter | None = None


def _try_redis():
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(redis_client=_try_redis())
    return _limiter


def reset_limiter_for_tests(redis_client: Any | None = None) -> RateLimiter:
    global _limiter
    _limiter = RateLimiter(redis_client=redis_client)
    return _limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket / sliding-window limiter (Redis when configured)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        path = request.url.path
        method = request.method.upper()
        limiter = get_limiter()
        try:
            if path == "/ingest" and method == "POST":
                limiter.check("ingest", settings.rate_limit_ingest_per_hour, 3600)
            elif path == "/search" and method == "GET":
                limiter.check("search", settings.rate_limit_search_per_minute, 60)
            elif path == "/query" and method == "POST":
                limiter.check("query", settings.rate_limit_query_per_minute, 60)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return await call_next(request)
