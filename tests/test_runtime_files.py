import base64
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from scanner.api.app import app
from scanner.api.files import managed_file_response
from scanner.config.paths import ApplicationPaths
from scanner.desktop.sidecar import create_desktop_app


def report_id(relative):
    return base64.urlsafe_b64encode(str(relative).encode()).decode()


@pytest.fixture
def managed(tmp_path, monkeypatch):
    for key, relative in {"SCANNER_DATA_ROOT": "application", "SCANNER_CACHE_ROOT": "cache",
                           "SCANNER_REPORT_ROOT": "application/reports", "SCANNER_LOG_ROOT": "logs"}.items():
        monkeypatch.setenv(key, str(tmp_path / relative))
    paths = ApplicationPaths.resolve()
    for root in (paths.reports, paths.logs, paths.exports):
        root.mkdir(parents=True)
    return paths


def test_runtime_contract_is_read_only_and_advertises_only_implemented_capabilities(managed, monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "fixture-secret-must-not-appear")
    before = sorted(managed.root.rglob("*"))
    with TestClient(app) as client:
        response = client.get("/api/v1/runtime")
    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == 1 and data["api_versions"] == [1]
    assert data["mode"] == "browser" and data["compatibility_api"] == "/api"
    assert data["capabilities"]["report_files"] is True
    assert data["capabilities"]["business_records"] is True
    assert data["capabilities"]["native_keychain"] is False
    assert data["capabilities"]["native_file_dialogs"] is False
    assert data["paths"]["reports"] == str(managed.reports)
    assert "fixture-secret" not in response.text
    assert sorted(managed.root.rglob("*")) == before


def test_desktop_runtime_requires_auth_and_does_not_claim_full_scanner_or_file_support(managed):
    token = "test-runtime-token-" + "x" * 32
    with TestClient(create_desktop_app(token)) as client:
        assert client.get("/api/v1/runtime").status_code == 401
        response = client.get("/api/v1/runtime", headers={"Authorization": f"Bearer {token}"})
    data = response.json()
    assert data["mode"] == "desktop-proof-of-concept"
    assert data["compatibility_api"] is None
    assert data["capabilities"]["desktop_lifecycle"] is True
    assert data["capabilities"]["scanner_workflows"] is False
    assert data["capabilities"]["report_files"] is False
    assert token not in response.text


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_report_download_and_pdf_preview_retain_bytes_and_safe_headers(managed, prefix):
    pdf = managed.reports / "Résumé report.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfixture-pdf\n")
    with TestClient(app) as client:
        url = f"{prefix}/reports/{report_id(pdf.name)}"
        downloaded = client.get(url + "/download")
        viewed = client.get(url + "/view")
    assert downloaded.content == pdf.read_bytes() == viewed.content
    assert downloaded.headers["content-type"] == "application/pdf"
    assert "filename*=UTF-8''R%C3%A9sum%C3%A9%20report.pdf" in downloaded.headers["content-disposition"]
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert viewed.headers["content-disposition"].startswith("inline;")
    assert viewed.headers["x-content-type-options"] == "nosniff"
    assert downloaded.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("relative", ["../credentials/private.pdf", "nested/../../private.pdf", "./report.pdf", "nested//report.pdf", "secret.key", "scanner.sqlite", "snapshot.json", "folder.pdf"])
def test_download_rejects_traversal_and_non_report_files(managed, relative):
    (managed.reports / "secret.key").write_text("fixture-private")
    (managed.reports / "scanner.sqlite").write_text("fixture-private")
    (managed.reports / "snapshot.json").write_text("fixture-private")
    (managed.reports / "folder.pdf").mkdir()
    with TestClient(app) as client:
        assert client.get(f"/api/v1/reports/{report_id(relative)}/download").status_code == 404
        assert client.get(f"/api/reports/{report_id(relative)}/download").status_code == 404


def test_invalid_id_and_absolute_paths_are_rejected_by_versioned_api(managed):
    pdf = managed.reports / "report.pdf"
    pdf.write_bytes(b"%PDF-fixture")
    with TestClient(app) as client:
        assert client.get("/api/v1/reports/not-valid-base64!/download").status_code == 404
        assert client.get(f"/api/v1/reports/{report_id(pdf)}/download").status_code == 404
        # Existing browser links remain usable, but only inside the reports root.
        assert client.get(f"/api/reports/{report_id(pdf)}/download").content == pdf.read_bytes()


def test_report_ids_survive_working_directory_and_report_root_changes(managed, tmp_path, monkeypatch):
    relative = Path("saved") / "report.pdf"
    (managed.reports / relative.parent).mkdir()
    (managed.reports / relative).write_bytes(b"%PDF-original")
    new_root = tmp_path / "moved-reports"
    (new_root / relative.parent).mkdir(parents=True)
    (new_root / relative).write_bytes(b"%PDF-original")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCANNER_REPORT_ROOT", str(new_root))
    with TestClient(app) as client:
        assert client.get(f"/api/v1/reports/{report_id(relative)}/download").content == b"%PDF-original"


def test_download_refuses_file_and_directory_symlinks_and_named_pipes(managed, tmp_path):
    outside = tmp_path / "private.pdf"
    outside.write_bytes(b"private-data")
    (managed.reports / "link.pdf").symlink_to(outside)
    (managed.reports / "linked-directory").symlink_to(tmp_path, target_is_directory=True)
    os.mkfifo(managed.reports / "pipe.pdf")
    with TestClient(app) as client:
        for relative in ("link.pdf", "linked-directory/private.pdf", "pipe.pdf"):
            assert client.get(f"/api/v1/reports/{report_id(relative)}/download").status_code == 404


def test_html_download_is_allowed_but_never_inline_application_origin_content(managed):
    (managed.reports / "report.html").write_text("<h1>Report</h1>")
    with TestClient(app) as client:
        for prefix in ("/api", "/api/v1"):
            url = f"{prefix}/reports/{report_id('report.html')}"
            assert client.get(url + "/download").status_code == 200
            assert client.get(url + "/view").status_code == 415


def test_job_downloads_resolve_known_outputs_in_managed_roots_only(managed, monkeypatch):
    import scanner.api.files as files
    outputs = {}
    for root, name in ((managed.reports, "report.csv"), (managed.logs, "scan.log"), (managed.exports, "export.csv")):
        (root / name).write_text(name)
        outputs[name] = str(root / name)
    outputs.update({"private": str(managed.credential_database), "cwd": "output/old.csv",
                    "escape": str(managed.reports / "../credentials/private.csv")})
    job = SimpleNamespace(progress=SimpleNamespace(output_paths=outputs))
    monkeypatch.setattr(files, "jobs", SimpleNamespace(get=lambda id: job if id == "known-job" else None))
    with TestClient(app) as client:
        for name in ("report.csv", "scan.log", "export.csv"):
            assert client.get(f"/api/v1/jobs/known-job/outputs/{name}/download").text == name
        for name in ("private", "cwd", "escape", "unknown"):
            assert client.get(f"/api/v1/jobs/known-job/outputs/{name}/download").status_code == 404
        assert client.get("/api/v1/jobs/missing/outputs/scan.log/download").status_code == 404


def test_open_descriptor_prevents_path_replacement_from_redirecting_download(managed, tmp_path):
    original = managed.reports / "report.pdf"
    original.write_bytes(b"%PDF-safe")
    private = tmp_path / "private.pdf"
    private.write_bytes(b"do-not-return")
    server = FastAPI()

    @server.get("/download")
    def download():
        response = managed_file_response(managed.reports, original.name)
        original.unlink()
        original.symlink_to(private)
        return response

    with TestClient(server) as client:
        assert client.get("/download").content == b"%PDF-safe"
