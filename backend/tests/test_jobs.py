from app.jobs import MemoryJobQueue


def test_memory_queue_enqueues_and_worker_processes():
    seen: list[int] = []

    def job(value: int) -> int:
        seen.append(value)
        return value * 2

    queue = MemoryJobQueue(auto_run=False)
    queued = queue.enqueue(job, 21)
    assert queued.done is False
    assert seen == []
    finished = queue.work_once()
    assert finished is not None
    assert finished.done is True
    assert finished.result == 42
    assert seen == [21]
