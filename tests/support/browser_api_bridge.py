"""NDJSON test transport to the real router/SQLite, with no network or providers.

Only the frontend integration test launches this process. All four managed roots
are mandatory and must be inside its newly created temporary test directory.
"""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile


def main():
    root = Path(sys.argv[1]).resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith("scanner-ui-api-test-"):
        raise ValueError("Bridge requires a fresh frontend test temporary directory")
    for key, relative in {"SCANNER_DATA_ROOT": "application", "SCANNER_CACHE_ROOT": "cache",
                           "SCANNER_REPORT_ROOT": "application/reports", "SCANNER_LOG_ROOT": "logs"}.items():
        os.environ[key] = str(root / relative)

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from scanner.api.business_records import router
    from scanner.api.files import router as files_router
    from scanner.api.runtime import router as runtime_router
    from scanner.api.setup import router as setup_router
    from scanner.data.ownership import application_lifespan

    app = FastAPI(lifespan=application_lifespan)
    app.include_router(router)
    app.include_router(files_router)
    app.include_router(runtime_router)
    app.include_router(setup_router)
    reports = root / "application/reports"
    reports.mkdir(parents=True, exist_ok=True)
    pdf = reports / "Résumé report.pdf"
    if not pdf.exists():
        pdf.write_bytes(b"%PDF-fixture-from-python")
    with TestClient(app) as client:
        print(json.dumps({"ready": True}), flush=True)
        for line in sys.stdin:
            request = json.loads(line)
            response = client.request(request.get("method", "GET"), request["path"], json=request.get("body"))
            print(json.dumps({"id": request["id"], "status": response.status_code,
                              "headers": dict(response.headers),
                              "content": base64.b64encode(response.content).decode()}), flush=True)


if __name__ == "__main__":
    main()
