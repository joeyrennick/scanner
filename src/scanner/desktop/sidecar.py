from __future__ import annotations

from collections.abc import Callable
import os
import platform
import secrets
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn


DESKTOP_HOST = "127.0.0.1"
DESKTOP_PORT_ENV = "SCANNER_DESKTOP_PORT"
DESKTOP_TOKEN_ENV = "SCANNER_DESKTOP_TOKEN"
MINIMUM_TOKEN_LENGTH = 32
ALLOWED_DESKTOP_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


def dependency_versions() -> dict[str, str]:
    """Import native-heavy dependencies and report the versions that loaded."""
    import certifi
    import lxml.etree
    import matplotlib
    import numpy
    import pandas
    import PIL

    return {
        "certifi": certifi.__version__,
        "lxml": ".".join(str(part) for part in lxml.etree.LXML_VERSION),
        "matplotlib": matplotlib.__version__,
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "pillow": PIL.__version__,
        "uvicorn": uvicorn.__version__,
    }


def create_desktop_app(
    token: str,
    shutdown_callback: Callable[[], None] | None = None,
) -> FastAPI:
    _validate_token(token)
    loaded_dependencies = dependency_versions()

    app = FastAPI(
        title="Swing Scanner Desktop Sidecar",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_DESKTOP_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def require_desktop_token(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        scheme, _, supplied_token = authorization.partition(" ")
        authenticated = scheme.lower() == "bearer" and secrets.compare_digest(
            supplied_token,
            token,
        )
        if not authenticated:
            return JSONResponse(
                status_code=401,
                content={"detail": "Desktop authentication required"},
            )

        return await call_next(request)

    @app.get("/api/desktop/health")
    def desktop_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "application": "Swing Scanner",
            "mode": "desktop-proof-of-concept",
            "sidecar_version": "0.1.0",
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
            "process_id": os.getpid(),
            "dependencies": loaded_dependencies,
        }

    @app.post("/api/desktop/shutdown", status_code=202)
    def desktop_shutdown(background_tasks: BackgroundTasks) -> dict[str, str]:
        if shutdown_callback is not None:
            background_tasks.add_task(shutdown_callback)
        return {"status": "shutting_down"}

    return app


def main() -> None:
    port = _desktop_port()
    token = os.environ.get(DESKTOP_TOKEN_ENV, "")
    _validate_token(token)

    server_holder: dict[str, uvicorn.Server] = {}

    def request_shutdown() -> None:
        server_holder["server"].should_exit = True

    app = create_desktop_app(token=token, shutdown_callback=request_shutdown)
    config = uvicorn.Config(
        app=app,
        host=DESKTOP_HOST,
        port=port,
        log_level="info",
        access_log=False,
        server_header=False,
    )
    server = uvicorn.Server(config)
    server_holder["server"] = server
    server.run()


def _desktop_port() -> int:
    raw_port = os.environ.get(DESKTOP_PORT_ENV, "")
    try:
        port = int(raw_port)
    except ValueError as error:
        raise RuntimeError(f"{DESKTOP_PORT_ENV} must contain a valid port") from error

    if port < 1 or port > 65535:
        raise RuntimeError(f"{DESKTOP_PORT_ENV} must be between 1 and 65535")
    return port


def _validate_token(token: str) -> None:
    if len(token) < MINIMUM_TOKEN_LENGTH:
        raise RuntimeError(
            f"{DESKTOP_TOKEN_ENV} must contain at least {MINIMUM_TOKEN_LENGTH} characters"
        )


if __name__ == "__main__":
    main()
