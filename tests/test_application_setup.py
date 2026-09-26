from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from scanner.api.app import app
from scanner.config.application import (
    ConfigurationConflict, ConfigurationUnavailable, SECIdentity,
    effective_sec_identity, read_configuration, save_sec_identity,
)
from scanner.config.paths import ApplicationPaths
from scanner.data.providers.sec import SECFundamentalsProvider
from scanner.migration.ownership import DataRootOwnership


@pytest.fixture
def managed(tmp_path, monkeypatch):
    for key, relative in {"SCANNER_DATA_ROOT": "application", "SCANNER_CACHE_ROOT": "cache",
                           "SCANNER_REPORT_ROOT": "application/reports", "SCANNER_LOG_ROOT": "logs"}.items():
        monkeypatch.setenv(key, str(tmp_path / relative))
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    return ApplicationPaths.resolve()


def identity(email="test@example.com"):
    return SECIdentity(application_name="Scanner Tests", contact_email=email)


def test_read_does_not_create_configuration_or_apply_archived_settings(managed):
    assert read_configuration().revision == 0
    assert not managed.root.exists()
    archive = managed.application_settings.parent / "scanner-settings.json"
    archive.parent.mkdir(parents=True)
    archive.write_text(json.dumps({"settings": {"sec_user_agent": "Old developer old@example.com", "output_file": "/old/source/output"}}))
    before = archive.read_bytes()
    with TestClient(app) as client:
        response = client.get("/api/v1/setup")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["sec_source"] == "missing"
        assert not response.json()["sec_configured"]
        assert client.get("/api/settings").json()["sec_user_agent"] == ""
    assert not managed.application_settings.exists()
    assert archive.read_bytes() == before


def test_save_survives_process_restart_and_uses_private_permissions(managed, monkeypatch, tmp_path):
    saved = save_sec_identity(identity(), 0)
    assert saved.revision == 1
    assert managed.application_settings.stat().st_mode & 0o777 == 0o600
    monkeypatch.chdir(tmp_path)
    assert read_configuration() == saved
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run([sys.executable, "-c", "from scanner.config.application import effective_sec_identity; print(effective_sec_identity().user_agent)"],
                            env=environment, cwd=tmp_path, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == identity().user_agent
    assert sorted(path.name for path in managed.application_settings.parent.iterdir()) == ["application-settings.json"]


def test_environment_and_explicit_precedence_never_overwrite_saved_identity(managed, monkeypatch):
    save_sec_identity(identity(), 0)
    before = managed.application_settings.read_bytes()
    assert effective_sec_identity().source == "saved"
    monkeypatch.setenv("SEC_USER_AGENT", "Launcher launcher@example.com")
    assert effective_sec_identity().source == "environment"
    assert SECFundamentalsProvider().user_agent == "Launcher launcher@example.com"
    assert SECFundamentalsProvider(user_agent="Explicit explicit@example.com").user_agent == "Explicit explicit@example.com"
    assert managed.application_settings.read_bytes() == before
    monkeypatch.delenv("SEC_USER_AGENT")
    assert effective_sec_identity().user_agent == identity().user_agent


@pytest.mark.parametrize("value", ["", " ", "missing-email", "just@example.com", "App a@example.com\r\nInjected: yes", "App a@example.com\n", "Scannér a@example.com"])
def test_invalid_launcher_identity_blocks_fallback_without_echoing_value(managed, monkeypatch, value):
    save_sec_identity(identity(), 0)
    monkeypatch.setenv("SEC_USER_AGENT", value)
    with TestClient(app) as client:
        status = client.get("/api/v1/setup").json()
        assert status["sec_source"] == "environment" and not status["sec_configured"]
        assert status["sec_user_agent"] == "" and status["sec_error"]
        assert client.get("/api/settings").status_code == 409
    with pytest.raises(ConfigurationUnavailable):
        SECFundamentalsProvider()


def test_provider_snapshot_uses_saved_contact_for_next_instance_no_validation_network(managed, monkeypatch):
    calls = []
    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"fixture": True}
    def request(_url, *, headers, timeout):
        calls.append(headers["User-Agent"])
        return FakeResponse()
    monkeypatch.setattr("scanner.data.providers.sec.requests.get", request)
    save_sec_identity(identity(), 0)
    previous = SECFundamentalsProvider()
    save_sec_identity(identity("new@example.com"), 1)
    current = SECFundamentalsProvider()
    assert calls == []
    assert previous._get_json("https://example.invalid/fixture") == {"fixture": True}
    current._get_json("https://example.invalid/fixture")
    assert calls == [identity().user_agent, identity("new@example.com").user_agent]


def test_revision_conflict_and_remove_recreate_prevent_overwrite(managed):
    with TestClient(app) as client:
        body = {"expected_revision": 0, "sec_identity": identity().model_dump()}
        assert client.put("/api/v1/setup", json=body).json()["configuration"]["revision"] == 1
        assert client.get("/api/settings").json()["sec_user_agent"] == identity().user_agent
        assert client.put("/api/v1/setup", json=body).status_code == 409
        assert client.put("/api/v1/setup", json={"expected_revision": 1, "sec_identity": None}).json()["configuration"]["revision"] == 2
        assert client.put("/api/v1/setup", json=body).status_code == 409
        assert client.get("/api/v1/setup").json()["sec_source"] == "missing"


@pytest.mark.parametrize("changes", [
    {"expected_revision": True}, {"expected_revision": "0"}, {"expected_revision": -1},
    {"unexpected": "value"}, {"sec_identity": {"application_name": "App", "contact_email": "bad"}},
    {"sec_identity": {"application_name": "App\r\nOther", "contact_email": "a@example.com"}},
    {"sec_identity": {"application_name": "App", "contact_email": "a@example.com\n"}},
    {"sec_identity": {"application_name": "App", "contact_email": "a@example.com", "password": "not-allowed"}},
    {"sec_identity": {"application_name": " " * 4, "contact_email": "a@example.com"}},
])
def test_api_rejects_invalid_setup_without_writes(managed, changes):
    with TestClient(app) as client:
        response = client.put("/api/v1/setup", json={"expected_revision": 0, "sec_identity": identity().model_dump(), **changes})
        assert response.status_code == 422
    assert not managed.application_settings.exists()


@pytest.mark.parametrize("data", [
    b"not-json", b'{"schema_version":2,"revision":1,"sec_identity":null}',
    b'{"schema_version":true,"revision":1,"sec_identity":null}',
    b'{"schema_version":1,"revision":1,"revision":2,"sec_identity":null}',
    b'{"schema_version":1,"revision":0,"sec_identity":null}',
    b'{"schema_version":1,"revision":1}', b" " * 8193,
])
def test_invalid_configuration_is_preserved_and_not_treated_as_empty(managed, data):
    managed.application_settings.parent.mkdir(parents=True)
    managed.application_settings.write_bytes(data)
    with TestClient(app) as client:
        assert client.get("/api/v1/setup").status_code == 409
        assert client.put("/api/v1/setup", json={"expected_revision": 0, "sec_identity": identity().model_dump()}).status_code == 409
    assert managed.application_settings.read_bytes() == data


@pytest.mark.parametrize("kind", ["directory-link", "file-link", "fifo"])
def test_configuration_refuses_symlinks_and_nonregular_files(managed, tmp_path, kind):
    external = tmp_path / "external"
    external.mkdir()
    target = external / "application-settings.json"
    target.write_text("untouched")
    managed.root.mkdir()
    if kind == "directory-link":
        managed.application_settings.parent.symlink_to(external, target_is_directory=True)
    else:
        managed.application_settings.parent.mkdir()
        if kind == "file-link":
            managed.application_settings.symlink_to(target)
        else:
            os.mkfifo(managed.application_settings)
    with pytest.raises(ConfigurationUnavailable):
        read_configuration()
    with pytest.raises(ConfigurationUnavailable):
        save_sec_identity(identity(), 0)
    assert target.read_text() == "untouched"


def test_concurrent_saves_admit_only_one_revision(managed):
    def attempt(_):
        try:
            return save_sec_identity(identity(), 0).revision
        except ConfigurationConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    assert sorted(results, key=str) == [1, "conflict"]
    assert read_configuration().revision == 1


def test_configuration_respects_another_process_owner(managed):
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    code = "from scanner.config.application import save_sec_identity; save_sec_identity(None, 0)"
    with DataRootOwnership(managed.root):
        result = subprocess.run([sys.executable, "-c", code], env=environment, capture_output=True, text=True)
    assert result.returncode != 0 and "Data root is in use" in result.stderr
    assert not managed.application_settings.exists()


def test_failed_atomic_replacement_preserves_old_configuration(managed, monkeypatch):
    save_sec_identity(identity(), 0)
    before = managed.application_settings.read_bytes()
    def fail(*_args, **_kwargs): raise OSError("simulated replace failure")
    monkeypatch.setattr("scanner.config.application.os.replace", fail)
    with pytest.raises(ConfigurationUnavailable):
        save_sec_identity(identity("new@example.com"), 1)
    assert managed.application_settings.read_bytes() == before
    assert sorted(path.name for path in managed.application_settings.parent.iterdir()) == ["application-settings.json"]
