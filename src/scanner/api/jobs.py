from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Callable
from uuid import uuid4


JobStatus = str


@dataclass
class JobRecord:
    job_id: str
    job_type: str
    status: JobStatus = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str = ""
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "message": self.message,
            "result": self.result,
            "error": self.error,
        }


class JobRegistry:
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def start(
        self,
        job_type: str,
        work: Callable[[], dict[str, Any]],
    ) -> JobRecord:
        job = JobRecord(job_id=str(uuid4()), job_type=job_type)

        with self._lock:
            self._jobs[job.job_id] = job

        self._executor.submit(self._run, job.job_id, work)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def _run(self, job_id: str, work: Callable[[], dict[str, Any]]) -> None:
        self._update(
            job_id,
            status="running",
            started_at=datetime.now(UTC),
            message="Running",
        )

        try:
            result = work()
        except Exception as error:
            self._update(
                job_id,
                status="failed",
                finished_at=datetime.now(UTC),
                message="Failed",
                error=str(error),
            )
            return

        status = "stopped" if result.get("stopped_for_rate_limit") else "complete"
        self._update(
            job_id,
            status=status,
            finished_at=datetime.now(UTC),
            message="Stopped" if status == "stopped" else "Complete",
            result=result,
        )

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for name, value in changes.items():
                setattr(job, name, value)


jobs = JobRegistry()

