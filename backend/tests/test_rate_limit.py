from app.rate_limit import RateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.z: dict[str, dict[str, float]] = {}

    def pipeline(self):
        return _FakePipe(self)


class _FakePipe:
    def __init__(self, store: FakeRedis) -> None:
        self.store = store
        self.ops = []

    def zremrangebyscore(self, key, lo, hi):
        self.ops.append(("zrem", key, lo, hi))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        out = []
        for op in self.ops:
            if op[0] == "zrem":
                _, key, lo, hi = op
                z = self.store.z.setdefault(key, {})
                self.store.z[key] = {k: v for k, v in z.items() if not (lo <= v <= hi)}
                out.append(1)
            elif op[0] == "zcard":
                out.append(len(self.store.z.get(op[1], {})))
            elif op[0] == "zadd":
                self.store.z.setdefault(op[1], {}).update(op[2])
                out.append(1)
            else:
                out.append(True)
        self.ops = []
        return out


def test_memory_limiter_blocks_after_limit():
    limiter = RateLimiter()
    assert limiter.allow("k", 2, 60)
    assert limiter.allow("k", 2, 60)
    assert limiter.allow("k", 2, 60) is False


def test_redis_limiter_sliding_window():
    limiter = RateLimiter(redis_client=FakeRedis())
    assert limiter.allow("u", 2, 60)
    assert limiter.allow("u", 2, 60)
    assert limiter.allow("u", 2, 60) is False
