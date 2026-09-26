"""Crash recovery for first-import activation; requires the caller's OS ownership.

Only previously absent fixed destination slots may be activated. An external
journal gates every runtime open. Before commit we roll back to the prior empty
destination; after commit we finish retiring the gate. Original files, failed
stages, and journals are retained, never deleted by recovery.
"""
import json
from pathlib import Path
import re

from scanner.migration.files import json_bytes, move_new, write_marker, write_new
from scanner.migration.legacy import sha256_file
from scanner.migration.ownership import DataRootOwnership, root_identity

SLOTS = ("data", "reports", "credentials", "configuration")


def tree_manifest(root: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid migration directory")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlinks are not allowed in staged migration data")
        if path.is_file():
            result[str(path.relative_to(root))] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return result


def checkpoint(_name: str):
    """Fault-injection boundary; production has no side effects."""


def _journal_path(owner: DataRootOwnership) -> Path:
    return owner.control_directory / "activation.json"


def _read_journal(owner: DataRootOwnership) -> tuple[dict, Path]:
    path = _journal_path(owner)
    if path.is_symlink() or path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Invalid activation journal; keep the root stopped for recovery")
    journal = json.loads(path.read_bytes())
    if (journal.get("version") != 1 or journal.get("root_identity") != root_identity(owner.root)
            or not re.fullmatch(r"[0-9a-f]{32}", journal.get("import_id", ""))
            or journal.get("state") not in {"activating", "committed"}
            or set(journal.get("slots", {})) != set(SLOTS)):
        raise ValueError("Unsupported activation journal; keep the root stopped for recovery")
    stage = owner.root / ".migration/stages" / journal["import_id"]
    if any(path.is_symlink() for path in (stage, stage.parent, stage.parent.parent)):
        raise ValueError("Symlink in activation staging path")
    return journal, stage


def recover_activation_locked(owner: DataRootOwnership) -> str | None:
    if owner._fd is None:
        raise RuntimeError("Recovery requires held data-root ownership")
    if not _journal_path(owner).exists():
        return None
    journal, stage = _read_journal(owner)
    committed = journal["state"] == "committed"
    # Validate the entire generation before moving anything on recovery.
    for slot in SLOTS:
        target, staged = owner.root / slot, stage / slot
        if committed:
            if staged.exists() or tree_manifest(target) != journal["slots"][slot]:
                raise ValueError("Committed import changed before recovery; keep the root stopped")
        else:
            if target.exists() == staged.exists():
                raise ValueError("Ambiguous partial activation; keep the root stopped")
            if tree_manifest(target if target.exists() else staged) != journal["slots"][slot]:
                raise ValueError("Partial import changed before recovery; keep the root stopped")
    if committed:
        gate = owner.root / "migration-pending.json"
        if gate.exists():
            gate_value = json.loads(gate.read_bytes())
            if gate_value.get("backup_id") != journal["backup_id"]:
                raise ValueError("Pending gate belongs to a different backup")
            move_new(gate, stage / "pending-import.original.json")
        checkpoint("gate-retired")
        # Pairing is never inherited from imported data; Phase 5 enforces this boundary.
        write_marker(owner.control_directory / "companion-state.json", {
            "version": 1, "companion_enabled": False, "pairing_reset_required": True,
            "import_id": journal["import_id"],
        })
    else:
        for slot in reversed(SLOTS):
            target = owner.root / slot
            if target.exists():
                move_new(target, stage / slot)
                checkpoint(f"rollback-{slot}")
    outcome = "committed" if committed else "rolled-back"
    move_new(_journal_path(owner), owner.control_directory / "history" / f"{journal['import_id']}-{outcome}.json")
    return outcome


def activate_locked(owner: DataRootOwnership, stage: Path, backup_id: str):
    if owner._fd is None:
        raise RuntimeError("Activation requires held data-root ownership")
    expected_stage = owner.root / ".migration/stages" / stage.name
    if stage != expected_stage or not re.fullmatch(r"[0-9a-f]{32}", stage.name):
        raise ValueError("Invalid activation stage")
    if _journal_path(owner).exists() or any((owner.root / slot).exists() for slot in SLOTS):
        raise ValueError("Import requires unused destination slots; existing data will not be replaced")
    journal = {"version": 1, "root_identity": root_identity(owner.root), "import_id": stage.name,
               "backup_id": backup_id, "state": "activating",
               "slots": {slot: tree_manifest(stage / slot) for slot in SLOTS}}
    write_new(_journal_path(owner), json_bytes(journal))
    checkpoint("journal-written")
    try:
        for slot in SLOTS:
            move_new(stage / slot, owner.root / slot)
            checkpoint(f"activated-{slot}")
        for slot in SLOTS:
            if tree_manifest(owner.root / slot) != journal["slots"][slot]:
                raise ValueError("Activated files failed reconciliation")
        checkpoint("before-commit")
        write_marker(_journal_path(owner), {**journal, "state": "committed"})
        checkpoint("after-commit")
        recover_activation_locked(owner)
    except Exception:
        # Process death skips this handler; the next owner runs the same recovery.
        recover_activation_locked(owner)
        raise
