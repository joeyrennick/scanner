"""ID-based file access. Client-supplied filesystem paths are never accepted."""
import base64
import os
from pathlib import Path, PurePosixPath
import stat
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from scanner.api.jobs import jobs
from scanner.config.paths import ApplicationPaths

router = APIRouter(prefix="/api/v1")
MEDIA_TYPES = {".pdf": "application/pdf", ".csv": "text/csv", ".html": "text/html", ".log": "text/plain"}


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="File not found or unavailable for download")


def report_relative(report_id: str, root: Path, *, legacy_absolute: bool = False) -> str:
    try:
        relative = base64.b64decode(report_id, altchars=b"-_", validate=True).decode("utf-8")
        if legacy_absolute and Path(relative).is_absolute():
            relative = str(Path(relative).relative_to(root))
        _parts(relative)
        return relative
    except (ValueError, UnicodeError, TypeError) as error:
        raise _not_found() from error


def _parts(relative: str) -> tuple[str, ...]:
    if (not relative or "\\" in relative or "\x00" in relative or relative.startswith("/")
            or any(part in {"", ".", ".."} for part in relative.split("/"))):
        raise ValueError("Invalid managed relative path")
    return PurePosixPath(relative).parts


def managed_file_response(root: Path, relative: str, *, inline: bool = False) -> StreamingResponse:
    """Walk directory descriptors without following symlinks; stream the opened file.

    Renaming/replacing a path after validation cannot redirect this response into
    credentials or another directory. A growing log is limited to its opening size.
    """
    directory = None
    descriptor = None
    try:
        parts = _parts(relative)
        media_type = MEDIA_TYPES.get(Path(parts[-1]).suffix.lower())
        if not media_type:
            raise _not_found()
        if inline and media_type != "application/pdf":
            raise HTTPException(status_code=415, detail="Only PDF reports support inline preview; download this file instead")
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in parts[:-1]:
            next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = next_directory
        descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise _not_found()
        opened = os.fdopen(descriptor, "rb")
        descriptor = None
    except (OSError, ValueError) as error:
        raise _not_found() from error
    finally:
        if directory is not None:
            os.close(directory)
        if descriptor is not None:
            os.close(descriptor)

    def content():
        remaining = info.st_size
        try:
            while remaining:
                chunk = opened.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        finally:
            opened.close()

    disposition = "inline" if inline else "attachment"
    return StreamingResponse(
        content(), media_type=media_type, background=BackgroundTask(opened.close),
        headers={"Content-Length": str(info.st_size),
                 "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(parts[-1], safe='')}",
                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                 "Content-Security-Policy": "sandbox"},
    )


@router.get("/reports/{report_id}/download")
def download_report(report_id: str):
    root = ApplicationPaths.resolve().reports
    return managed_file_response(root, report_relative(report_id, root))


@router.get("/reports/{report_id}/view")
def view_report(report_id: str):
    root = ApplicationPaths.resolve().reports
    return managed_file_response(root, report_relative(report_id, root), inline=True)


@router.get("/jobs/{job_id}/outputs/{output_name}/download")
def download_job_output(job_id: str, output_name: str):
    job = jobs.get(job_id)
    path_text = job.progress.output_paths.get(output_name) if job else None
    if not isinstance(path_text, str):
        raise _not_found()
    path = Path(path_text)
    if not path.is_absolute():
        # No cwd/repository fallback for historical or arbitrary job paths.
        raise _not_found()
    paths = ApplicationPaths.resolve()
    for root in (paths.reports, paths.logs, paths.exports):
        try:
            relative = str(path.relative_to(root))
        except ValueError:
            continue
        return managed_file_response(root, relative)
    raise _not_found()
