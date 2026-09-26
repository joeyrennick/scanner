"""Preview and first-import of a verified coordinated backup into unused slots."""
import base64
from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path, PurePosixPath
import sqlite3
from uuid import uuid4

from scanner.config.paths import ApplicationPaths
from scanner.data.browser_records import import_browser_snapshot
from scanner.data.schema import migrate_legacy_snapshot
from scanner.migration.activation import SLOTS, activate_locked, recover_activation_locked
from scanner.migration.backup import _decrypt_recovery, _disjoint, _validate_credentials
from scanner.migration.browser import validate_browser_export
from scanner.migration.files import json_bytes, write_marker, write_new
from scanner.migration.legacy import (
    BUSINESS_TABLES, check_database, read_database, record_manifest,
    require_stopped_source, sha256_file, snapshot, source_files,
)
from scanner.migration.ownership import DataRootOwnership, root_identity


def _load_json(path: Path, limit: int = 5 * 1024 * 1024) -> dict:
    if path.is_symlink() or path.stat().st_size > limit:
        raise ValueError(f"Invalid migration metadata: {path.name}")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Invalid migration metadata: {path.name}")
    return value


def load_verified_backup(backup: Path, verification_root: Path) -> tuple[dict, dict]:
    manifest = _load_json(backup / "manifest.json")
    if (manifest.get("format") != "swing-scanner.legacy-backup" or manifest.get("version") != 1
            or manifest.get("source_user_version") != 0):
        raise ValueError("Unsupported backup version")
    files = manifest.get("files")
    if not isinstance(files, dict) or len(files) > 10000:
        raise ValueError("Invalid backup file manifest")
    for relative, metadata in files.items():
        parsed = PurePosixPath(relative)
        if (parsed.is_absolute() or ".." in parsed.parts or str(parsed) != relative
                or not parsed.parts or "\\" in relative or relative == "manifest.json"):
            raise ValueError("Unsafe backup path")
        file = backup / relative
        if any(part.is_symlink() for part in (file, *file.parents) if part != backup.parent):
            raise ValueError("Symlinks are not allowed in backup paths")
        if file.stat().st_size != metadata["bytes"] or sha256_file(file) != metadata["sha256"]:
            raise ValueError("Backup checksum mismatch")
    actual = {str(file.relative_to(backup)) for file in backup.rglob("*") if file.is_file()}
    required = {"data/business.sqlite", "browser-export.json", "configuration/scanner-settings.json"}
    if actual != files.keys() | {"manifest.json"} or not required <= files.keys():
        raise ValueError("Missing or unexpected backup files")
    count = manifest.get("credential_count")
    if type(count) is not int or count < 0 or (count > 0) != ("credential-recovery.enc" in files):
        raise ValueError("Invalid credential recovery manifest")
    verification = _load_json(verification_root / "verification.json")
    for field in ("backup_id", "business_records", "browser_counts"):
        if verification.get(field) != manifest.get(field):
            raise ValueError("Isolated restore evidence does not match this backup")
    if (verification.get("credentials_decrypted") != manifest.get("credential_count")
            or verification.get("files_verified") != len(files)
            or verification.get("active_store_imported") is not False
            or not verification.get("verified_at")):
        raise ValueError("Successful isolated restore evidence is required before import")
    browser = validate_browser_export((backup / "browser-export.json").read_bytes())
    if browser["counts"] != manifest["browser_counts"] or browser["source"] != manifest["browser_source"]:
        raise ValueError("Browser backup does not reconcile")
    with read_database(backup / "data/business.sqlite") as database:
        check_database(database)
        if record_manifest(database, BUSINESS_TABLES) != manifest["business_records"]:
            raise ValueError("Business backup does not reconcile")
        # Validate/migrate only an in-memory copy, even during preview.
        with closing(sqlite3.connect(":memory:")) as staged:
            snapshot(database, staged)
            migrate_legacy_snapshot(staged, "business")
    return manifest, browser


def _validate_destination(root: Path, manifest: dict, manifest_digest: str) -> dict | None:
    receipt_path = root / "data/import-receipt.json"
    if receipt_path.exists():
        receipt = _load_json(receipt_path)
        if receipt.get("version") != 1 or receipt.get("active_store_imported") is not True:
            raise ValueError("Unsupported active import receipt; use recovery, not re-import")
        if receipt.get("backup_id") != manifest["backup_id"] or receipt.get("backup_manifest_sha256") != manifest_digest:
            raise ValueError("Destination already contains another import; it will not be overwritten")
        if not (root / "data/scanner.sqlite").is_file() or not (root / "data/browser-records.sqlite").is_file():
            raise ValueError("Imported store is incomplete; use recovery, not re-import")
        return receipt
    if any((root / slot).exists() or (root / slot).is_symlink() for slot in SLOTS):
        raise ValueError("Import requires unused destination slots; existing data will not be replaced")
    gate = root / "migration-pending.json"
    if gate.exists() and _load_json(gate).get("backup_id") != manifest["backup_id"]:
        raise ValueError("Pending migration belongs to a different backup")
    return None


def _check_layout(paths: ApplicationPaths, backup: Path, source: Path):
    if paths.reports != paths.root / "reports":
        raise ValueError("First import currently requires reports inside the selected root; custom report activation is not supported")
    _disjoint(paths.root, source)
    # A backup under root/backups is expected, but it must never occupy an active slot.
    for slot in SLOTS + (".migration",):
        _disjoint(paths.root / slot, backup)


def _check_source(source: Path, manifest: dict):
    require_stopped_source(source)
    inventory = source_files(source)
    if any(item["kind"] == "unclassified" for item in inventory):
        raise ValueError("New unclassified source files require review and a fresh backup")
    durable = {item["path"] for item in inventory if item["kind"] in {"durable-file", "durable-report"}}
    captured = {name.removeprefix("legacy-files/") for name in manifest["files"] if name.startswith("legacy-files/")}
    if durable != captured:
        raise ValueError("Source files changed after capture; export and back up again")
    for relative in durable:
        if sha256_file(source / relative) != manifest["files"]["legacy-files/" + relative]["sha256"]:
            raise ValueError("Source files changed after capture; export and back up again")
    with read_database(source / "market_data_cache.sqlite") as database:
        if database.execute("PRAGMA user_version").fetchone()[0] != manifest["source_user_version"]:
            raise ValueError("Source schema version changed after capture; review before importing")
        if record_manifest(database, BUSINESS_TABLES) != manifest["business_records"]:
            raise ValueError("Source business records changed after capture; export and back up again")
        from scanner.migration.legacy import KNOWN_TABLES, tables
        if (set(tables(database)) - KNOWN_TABLES
                or database.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger', 'view')").fetchone()):
            raise ValueError("Source schema changed after capture; review before importing")
        current_credentials = (database.execute("SELECT COUNT(*) FROM secrets").fetchone()[0]
                               if "secrets" in tables(database) else 0)
        if current_credentials != manifest["credential_count"]:
            raise ValueError("Source credentials changed after capture; create a new verified backup")


def preview_import(backup: Path, verification_root: Path, paths: ApplicationPaths) -> dict:
    backup, verification_root = backup.resolve(strict=True), verification_root.resolve(strict=True)
    with DataRootOwnership(paths.root) as owner, DataRootOwnership(backup):
        if owner.restore_marker.exists() or (owner.control_directory / "activation.json").exists():
            raise ValueError("Recover the pending activation/restore before previewing another import")
        manifest, _browser = load_verified_backup(backup, verification_root)
        _check_layout(paths, backup, Path(manifest["source_root"]))
        receipt = _validate_destination(paths.root, manifest, sha256_file(backup / "manifest.json"))
        return {"action": "already-imported" if receipt else "first-import", "destination": str(paths.root),
                "backup_id": manifest["backup_id"], "business_records": manifest["business_records"],
                "browser_counts": manifest["browser_counts"], "credential_count": manifest["credential_count"],
                "source_files_preserved": True, "replaces_existing_data": False}


def select_verified_backup(backup: Path, verification_root: Path, paths: ApplicationPaths,
                           *, expected_pending_backup_id: str, source_writers_stopped: bool) -> dict:
    """Reassociate an unused destination's gate after a fresh recovery exercise.

    This never imports data or retires the gate. Preserve the previous marker
    before atomically changing its backup reference; either reference remains
    a valid startup block if the operation is interrupted.
    """
    if not source_writers_stopped:
        raise ValueError("Stop source writers before selecting a replacement backup")
    backup, verification_root = backup.resolve(strict=True), verification_root.resolve(strict=True)
    with DataRootOwnership(paths.root) as owner, DataRootOwnership(backup):
        if owner.restore_marker.exists() or (owner.control_directory / "activation.json").exists():
            raise ValueError("Recover the pending activation/restore before selecting another backup")
        if any((paths.root / slot).exists() or (paths.root / slot).is_symlink() for slot in SLOTS):
            raise ValueError("Backup selection requires unused destination slots; existing data will not be replaced")
        gate_path = paths.root / "migration-pending.json"
        previous = _load_json(gate_path)
        if previous.get("version") != 1 or previous.get("state") != "awaiting-staged-import":
            raise ValueError("Unsupported pending-import gate")
        manifest, _browser = load_verified_backup(backup, verification_root)
        source = Path(manifest["source_root"]).resolve(strict=True)
        _check_layout(paths, backup, source)
        if previous.get("source_root") and root_identity(Path(previous["source_root"])) != root_identity(source):
            raise ValueError("Replacement backup belongs to a different source")
        digest = sha256_file(backup / "manifest.json")
        if previous.get("backup_id") == manifest["backup_id"]:
            if previous.get("backup_manifest_sha256", digest) != digest:
                raise ValueError("Selected backup manifest changed; review before continuing")
            return {"backup_id": manifest["backup_id"], "already_selected": True,
                    "active_store_imported": False, "startup_blocked": True}
        if previous.get("backup_id") != expected_pending_backup_id:
            raise ValueError("Pending backup selection changed; refresh before replacing it")
        with DataRootOwnership(source):
            _check_source(source, manifest)
            selection_id = uuid4().hex
            saved_gate = owner.control_directory / "history" / f"{selection_id}-prior-pending-import.json"
            write_new(saved_gate, gate_path.read_bytes())
            evidence = _load_json(verification_root / "verification.json")
            replacement = {**previous, "backup_id": manifest["backup_id"],
                           "backup_directory": str(backup), "verified_restore_directory": str(verification_root),
                           "source_root": str(source), "verified_at": evidence["verified_at"],
                           "backup_manifest_sha256": digest, "previous_backup_id": previous["backup_id"],
                           "selected_at": datetime.now(UTC).isoformat(), "selection_id": selection_id}
            write_marker(gate_path, replacement)
            return {"backup_id": manifest["backup_id"], "previous_backup_id": previous["backup_id"],
                    "prior_gate_preserved_at": str(saved_gate), "already_selected": False,
                    "active_store_imported": False, "startup_blocked": True}


def import_backup(backup: Path, verification_root: Path, paths: ApplicationPaths, passphrase: str,
                  *, source_writers_stopped: bool, browser_edits_paused: bool) -> dict:
    if not source_writers_stopped or not browser_edits_paused:
        raise ValueError("Stop source writers and keep original-browser editing paused before import")
    backup, verification_root = backup.resolve(strict=True), verification_root.resolve(strict=True)
    with DataRootOwnership(paths.root) as owner, DataRootOwnership(backup):
        if owner.restore_marker.exists():
            raise ValueError("Isolated restore roots cannot be activated through first import")
        recover_activation_locked(owner)
        manifest, browser = load_verified_backup(backup, verification_root)
        source = Path(manifest["source_root"]).resolve(strict=True)
        _check_layout(paths, backup, source)
        digest = sha256_file(backup / "manifest.json")
        existing = _validate_destination(paths.root, manifest, digest)
        if existing is not None:
            return {**existing, "already_imported": True}
        with DataRootOwnership(source):
            _check_source(source, manifest)
            credentials = None
            if manifest["credential_count"]:
                credentials = _decrypt_recovery((backup / "credential-recovery.enc").read_bytes(), passphrase)
                if _validate_credentials(credentials) != manifest["credential_count"]:
                    raise ValueError("Credential recovery count mismatch")
                # Reconcile the encrypted rows and original key without exposing values.
                from scanner.migration.backup import _credential_projection
                with read_database(source / "market_data_cache.sqlite") as database:
                    current = _credential_projection(database, source / "market_data_cache.key")
                if current is None or current["key"] != credentials["key"]:
                    raise ValueError("Source credentials changed after capture; create a new verified backup")
                with closing(sqlite3.connect(":memory:")) as left, closing(sqlite3.connect(":memory:")) as right:
                    left.deserialize(base64.b64decode(current["database"]))
                    right.deserialize(base64.b64decode(credentials["database"]))
                    if record_manifest(left, {"secrets"}) != record_manifest(right, {"secrets"}):
                        raise ValueError("Source credentials changed after capture; create a new verified backup")
            import_id = uuid4().hex
            stage = paths.root / ".migration/stages" / import_id
            stage.mkdir(mode=0o700, parents=True)
            for slot in SLOTS:
                (stage / slot).mkdir(mode=0o700)
            gate = paths.root / "migration-pending.json"
            if not gate.exists():
                write_new(gate, json_bytes({"version": 1, "backup_id": manifest["backup_id"],
                                           "state": "awaiting-staged-import"}))
            with read_database(backup / "data/business.sqlite") as source_db, closing(sqlite3.connect(":memory:")) as database:
                snapshot(source_db, database)
                migrate_legacy_snapshot(database, "business")
                check_database(database)
                if record_manifest(database, BUSINESS_TABLES) != manifest["business_records"]:
                    raise ValueError("Staged business data does not reconcile")
                write_new(stage / "data/scanner.sqlite", database.serialize())
            with closing(sqlite3.connect(":memory:")) as database:
                import_browser_snapshot(database, browser)
                database.commit()
                check_database(database)
                for collection, records in browser["collections"].items():
                    actual = [json.loads(row[0]) for row in database.execute(
                        "SELECT payload_json FROM business_records WHERE collection=? ORDER BY record_id", (collection,))]
                    if actual != sorted(records, key=lambda record: record["id"]):
                        raise ValueError("Staged browser data does not reconcile")
                write_new(stage / "data/browser-records.sqlite", database.serialize())
            if credentials is not None:
                with closing(sqlite3.connect(":memory:")) as database:
                    database.deserialize(base64.b64decode(credentials["database"]))
                    migrate_legacy_snapshot(database, "credential")
                    write_new(stage / "credentials/legacy.sqlite", database.serialize())
                write_new(stage / "credentials/legacy.key", credentials["key"].encode())
                credentials = None
            for relative in manifest["files"]:
                if relative.startswith("legacy-files/"):
                    name = relative.removeprefix("legacy-files/")
                    target = stage / ("data" if name == "trade_journal.csv" else "reports") / name
                    write_new(target, (backup / relative).read_bytes())
                elif relative.startswith("configuration/"):
                    write_new(stage / relative, (backup / relative).read_bytes())
            receipt = {"version": 1, "import_id": import_id, "backup_id": manifest["backup_id"],
                       "backup_manifest_sha256": digest, "imported_at": datetime.now(UTC).isoformat(),
                       "business_records": manifest["business_records"], "browser_counts": browser["counts"],
                       "browser_source": browser["source"], "credential_count": manifest["credential_count"],
                       "active_store_imported": True, "source_files_preserved": True}
            write_new(stage / "data/import-receipt.json", json_bytes(receipt))
            # Re-open the exact staged files before activation, not only memory objects.
            for name in ("data/scanner.sqlite", "data/browser-records.sqlite"):
                with read_database(stage / name) as database:
                    check_database(database)
            _check_source(source, manifest)
            if sha256_file(backup / "manifest.json") != digest:
                raise ValueError("Backup changed during staging")
            activate_locked(owner, stage, manifest["backup_id"])
            return {**receipt, "already_imported": False}
