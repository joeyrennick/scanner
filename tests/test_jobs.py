import time
from threading import Event

from scanner.api.jobs import JobRegistry


def test_job_registry_cancels_running_job():
    registry = JobRegistry(max_workers=1)
    started = Event()

    def work(progress, cancel_requested):
        progress(current_step="Waiting")
        started.set()

        for _attempt in range(100):
            if cancel_requested():
                return {"cancelled": True}
            time.sleep(0.01)

        raise AssertionError("cancel checker was not set")

    job = registry.start("scan", work)
    assert started.wait(timeout=1)

    cancelled_job = registry.cancel(job.job_id)
    assert cancelled_job is not None
    assert cancelled_job.cancel_requested is True

    for _attempt in range(100):
        current = registry.get(job.job_id)
        if current and current.status == "stopped":
            assert current.message == "Cancelled"
            assert current.result == {"cancelled": True}
            return
        time.sleep(0.01)

    raise AssertionError("job was not cancelled")
