"""Versioned, read-only connection contract shared by browser and desktop hosts."""
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from scanner.config.paths import ApplicationPaths


class RuntimeCapabilities(BaseModel):
    scanner_workflows: bool
    business_records: bool
    report_files: bool
    job_output_files: bool
    legacy_credential_controls: bool
    native_keychain: bool = False
    native_file_dialogs: bool = False
    desktop_lifecycle: bool


class RuntimePaths(BaseModel):
    data: str
    cache: str
    reports: str
    logs: str
    exports: str


class RuntimeInfo(BaseModel):
    schema_version: Literal[1] = 1
    application: Literal["Swing Scanner"] = "Swing Scanner"
    mode: Literal["browser", "desktop-proof-of-concept"]
    api_versions: list[int]
    compatibility_api: Literal["/api"] | None
    capabilities: RuntimeCapabilities
    paths: RuntimePaths


router = APIRouter(prefix="/api/v1")


@router.get("/runtime", response_model=RuntimeInfo)
def runtime_info(request: Request) -> RuntimeInfo:
    mode = getattr(request.app.state, "scanner_runtime_mode", "browser")
    browser = mode == "browser"
    paths = ApplicationPaths.resolve()
    return RuntimeInfo(
        mode=mode, api_versions=[1], compatibility_api="/api" if browser else None,
        capabilities=RuntimeCapabilities(
            scanner_workflows=browser, business_records=browser, report_files=browser,
            job_output_files=browser, legacy_credential_controls=browser,
            desktop_lifecycle=not browser,
        ),
        paths=RuntimePaths(data=str(paths.data), cache=str(paths.cache), reports=str(paths.reports),
                           logs=str(paths.logs), exports=str(paths.exports)),
    )
