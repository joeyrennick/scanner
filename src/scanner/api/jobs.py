from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Callable
from uuid import uuid4


JobStatus = str
ProgressUpdater = Callable[..., None]
CancelChecker = Callable[[], bool]


class JobCancelled(Exception):
    pass


@dataclass
class JobProgress:
    current_step: str | None = None
    total_steps: int | None = None
    symbols_total: int | None = None
    symbols_checked: int | None = None
    symbols_kept: int | None = None
    symbols_skipped: int | None = None
    provider_batches_attempted: int | None = None
    provider_batch_limit: int | None = None
    provider_symbols_attempted: int | None = None
    provider_symbol_limit: int | None = None
    elapsed_seconds: float | None = None
    estimated_seconds_remaining: float | None = None
    rate_limited: bool = False
    output_paths: dict[str, str] = field(default_factory=dict)

    def update(self, **changes: Any) -> None:
        for name, value in changes.items():
            if hasattr(self, name):
                setattr(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "symbols_total": self.symbols_total,
            "symbols_checked": self.symbols_checked,
            "symbols_kept": self.symbols_kept,
            "symbols_skipped": self.symbols_skipped,
            "provider_batches_attempted": self.provider_batches_attempted,
            "provider_batch_limit": self.provider_batch_limit,
            "provider_symbols_attempted": self.provider_symbols_attempted,
            "provider_symbol_limit": self.provider_symbol_limit,
            "elapsed_seconds": self.elapsed_seconds,
            "estimated_seconds_remaining": self.estimated_seconds_remaining,
            "rate_limited": self.rate_limited,
            "output_paths": self.output_paths,
        }


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
    progress: JobProgress = field(default_factory=JobProgress)
    cancel_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        progress = self.progress.to_dict()
        if self.started_at and progress["elapsed_seconds"] is None:
            end_time = self.finished_at or datetime.now(UTC)
            progress["elapsed_seconds"] = (end_time - self.started_at).total_seconds()
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
            "cancel_requested": self.cancel_requested,
            "progress": progress,
            **progress,
        }


class JobRegistry:
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def start(
        self,
        job_type: str,
        work: Callable[[ProgressUpdater, CancelChecker], dict[str, Any]],
    ) -> JobRecord:
        job = JobRecord(job_id=str(uuid4()), job_type=job_type)

        with self._lock:
            self._jobs[job.job_id] = job

        self._executor.submit(self._run, job.job_id, work)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)

            if job is None:
                return None

            if job.status in {"queued", "running"}:
                job.cancel_requested = True
                job.message = "Cancellation requested"

            return job

    def _run(
        self,
        job_id: str,
        work: Callable[[ProgressUpdater, CancelChecker], dict[str, Any]],
    ) -> None:
        self._update(
            job_id,
            status="running",
            started_at=datetime.now(UTC),
            message="Running",
        )

        try:
            result = work(
                lambda **changes: self.update_progress(job_id, **changes),
                lambda: self.is_cancel_requested(job_id),
            )
        except JobCancelled:
            self._update(
                job_id,
                status="stopped",
                finished_at=datetime.now(UTC),
                message="Cancelled",
                result={"cancelled": True},
            )
            return
        except Exception as error:
            self._update(
                job_id,
                status="failed",
                finished_at=datetime.now(UTC),
                message="Failed",
                error=str(error),
            )
            return

        cancelled = result.get("cancelled") or self.is_cancel_requested(job_id)
        status = "stopped" if result.get("stopped_for_rate_limit") or cancelled else "complete"
        output_paths = result.get("output_paths")
        if isinstance(output_paths, dict):
            self.update_progress(job_id, output_paths=output_paths)
        self._update(
            job_id,
            status=status,
            finished_at=datetime.now(UTC),
            message="Cancelled" if cancelled else ("Stopped" if status == "stopped" else "Complete"),
            result=result,
        )

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.cancel_requested)

    def update_progress(self, job_id: str, **changes: Any) -> None:
        message = changes.pop("message", None)

        with self._lock:
            job = self._jobs[job_id]
            job.progress.update(**changes)

            if message is not None:
                job.message = message

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for name, value in changes.items():
                setattr(job, name, value)


jobs = JobRegistry()
