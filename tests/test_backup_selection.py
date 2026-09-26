import json

import pytest

from scanner.data.ownership import acquire_root
from scanner.migration import importer
from scanner.migration.importer import preview_import, select_verified_backup
from scanner.migration.ownership import DataRootInUse, DataRootOwnership
from tests.test_staged_import import prepared  # Reuse the isolated real-schema backup fixture.

PREVIOUS_ID = "0" * 32


def make_gate(paths):
    paths.root.mkdir(parents=True)
    value = {"version": 1, "state": "awaiting-staged-import", "backup_id": PREVIOUS_ID}
    (paths.root / "migration-pending.json").write_text(json.dumps(value))
    return value


def select(prepared):
    _, backup, verification, paths = prepared
    return select_verified_backup(backup, verification, paths,
                                  expected_pending_backup_id=PREVIOUS_ID, source_writers_stopped=True)


def test_replacement_preserves_old_gate_and_keeps_runtime_blocked(prepared):
    _, backup, verification, paths = prepared
    previous = make_gate(paths)
    before = (paths.root / "migration-pending.json").read_bytes()
    result = select(prepared)
    current = json.loads((paths.root / "migration-pending.json").read_bytes())
    assert current["previous_backup_id"] == previous["backup_id"]
    assert current["backup_id"] == result["backup_id"]
    assert not result["active_store_imported"]
    from pathlib import Path
    assert Path(result["prior_gate_preserved_at"]).read_bytes() == before
    with pytest.raises(RuntimeError, match="Legacy migration is pending"):
        acquire_root(paths.root)
    assert not paths.data.exists()
    assert preview_import(backup, verification, paths)["action"] == "first-import"
    unchanged = (paths.root / "migration-pending.json").read_bytes()
    assert select(prepared)["already_selected"]
    assert (paths.root / "migration-pending.json").read_bytes() == unchanged


@pytest.mark.parametrize("problem", ["changed-gate", "invalid-evidence", "changed-source", "existing-data", "pending-activation", "different-source"])
def test_invalid_reselection_keeps_current_gate(prepared, problem):
    source, _, verification, paths = prepared
    gate = make_gate(paths)
    if problem == "changed-gate":
        gate["backup_id"] = "another-pending-backup"
    elif problem == "different-source":
        gate["source_root"] = str(source.parent / "different-source")
    elif problem == "invalid-evidence":
        evidence = verification / "verification.json"
        value = json.loads(evidence.read_bytes())
        value["credentials_decrypted"] = 0
        evidence.write_text(json.dumps(value))
    elif problem == "changed-source":
        (source / "watchlist.csv").write_text("changed source")
    elif problem == "existing-data":
        paths.data.mkdir()
        (paths.data / "user-file").write_text("keep")
    elif problem == "pending-activation":
        with DataRootOwnership(paths.root) as owner:
            (owner.control_directory / "activation.json").write_text("{}")
    gate_path = paths.root / "migration-pending.json"
    gate_path.write_text(json.dumps(gate))
    before = gate_path.read_bytes()
    with pytest.raises(ValueError):
        select(prepared)
    assert gate_path.read_bytes() == before


def test_selection_requires_ownership(prepared):
    _, _, _, paths = prepared
    make_gate(paths)
    with DataRootOwnership(paths.root):
        with pytest.raises(DataRootInUse):
            select(prepared)


def test_failed_atomic_replacement_preserves_old_gate(prepared, monkeypatch):
    _, _, _, paths = prepared
    make_gate(paths)
    before = (paths.root / "migration-pending.json").read_bytes()
    def fail(*_args):
        raise OSError("fixture failed atomic write")
    monkeypatch.setattr(importer, "write_marker", fail)
    with pytest.raises(OSError, match="fixture failed"):
        select(prepared)
    assert (paths.root / "migration-pending.json").read_bytes() == before
    assert not paths.data.exists()
