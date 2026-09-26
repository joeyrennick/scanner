"""Run with PYTHONPATH=src .venv313/bin/python -m scanner.migration."""
import argparse
import getpass
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from scanner.migration.backup import create_backup, verify_backup
from scanner.migration.legacy import inventory
from scanner.config.paths import ApplicationPaths
from scanner.migration.importer import import_backup, preview_import, select_verified_backup
from scanner.migration.activation import recover_activation_locked
from scanner.migration.ownership import DataRootOwnership


def main():
    parser = argparse.ArgumentParser(description="Explicit legacy inventory, backup, and isolated restore verification")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inventory", help="Read schema/counts and file metadata without initializing source stores")
    inspect.add_argument("--source-root", required=True, type=Path)
    backup = commands.add_parser("backup", help="Capture stopped legacy data; prompts privately for a recovery passphrase")
    backup.add_argument("--source-root", required=True, type=Path)
    backup.add_argument("--destination", required=True, type=Path)
    backup.add_argument("--browser-export", required=True, type=Path)
    backup.add_argument("--verify-root", type=Path,
                        help="After capture, prompt for the saved recovery passphrase and verify in this NEW root")
    backup.add_argument("--source-writers-stopped", action="store_true", required=True)
    verify = commands.add_parser("verify", help="Restore into a NEW isolated root and reconcile records and credentials")
    verify.add_argument("--backup", required=True, type=Path)
    verify.add_argument("--restore-root", required=True, type=Path)
    preview = commands.add_parser("preview-import", help="Validate a verified backup and preview first import without creating active stores")
    activate = commands.add_parser("import", help="Preview and import verified data into unused slots; prompts privately for the saved recovery passphrase")
    select = commands.add_parser("select-verified-backup", help="Update an unused destination gate to a newly verified backup; does not import data")
    for command in (preview, activate, select):
        command.add_argument("--backup", required=True, type=Path)
        command.add_argument("--verification-root", required=True, type=Path)
    activate.add_argument("--source-writers-stopped", action="store_true", required=True)
    activate.add_argument("--browser-edits-paused", action="store_true", required=True)
    select.add_argument("--expected-pending-backup-id", required=True)
    select.add_argument("--source-writers-stopped", action="store_true", required=True)
    commands.add_parser("recover-activation", help="Recover an interrupted first import under the selected root ownership lock")
    args = parser.parse_args()
    try:
        if args.command == "inventory":
            result = inventory(args.source_root)
        elif args.command == "select-verified-backup":
            result = select_verified_backup(args.backup, args.verification_root, ApplicationPaths.resolve(),
                                            expected_pending_backup_id=args.expected_pending_backup_id,
                                            source_writers_stopped=args.source_writers_stopped)
        elif args.command == "recover-activation":
            with DataRootOwnership(ApplicationPaths.resolve().root) as owner:
                result = {"recovery": recover_activation_locked(owner) or "not-required"}
        elif args.command in {"preview-import", "import"}:
            paths = ApplicationPaths.resolve()
            result = preview_import(args.backup, args.verification_root, paths)
            if args.command == "import" and result["action"] != "already-imported":
                print(json.dumps(result, indent=2))
                if not sys.stdin.isatty():
                    raise ValueError("Run import in a local terminal; never send the recovery passphrase through chat")
                if input("Import this verified backup into the unused destination shown above? Type IMPORT: ").strip() != "IMPORT":
                    raise ValueError("Import not confirmed; no active stores were changed")
                passphrase = getpass.getpass("Saved backup recovery passphrase (hidden): ")
                try:
                    result = import_backup(args.backup, args.verification_root, paths, passphrase,
                                           source_writers_stopped=args.source_writers_stopped,
                                           browser_edits_paused=args.browser_edits_paused)
                finally:
                    passphrase = None
        else:
            if not sys.stdin.isatty():
                raise ValueError("Run interactively: recovery passphrases must not appear in arguments, environment, or logs")
            passphrase = getpass.getpass("Recovery passphrase (stored separately in your password manager): ")
            if args.command == "backup":
                if passphrase != getpass.getpass("Confirm recovery passphrase: "):
                    raise ValueError("Recovery passphrases did not match")
                result = create_backup(args.source_root, args.destination, args.browser_export, passphrase,
                                       source_writers_stopped=args.source_writers_stopped)
                if args.verify_root is not None:
                    passphrase = None
                    print(f"Backup captured at {args.destination}. Retrieve the passphrase you saved separately to verify recovery.")
                    recovered_passphrase = getpass.getpass("Saved recovery passphrase for restore verification: ")
                    result = verify_backup(args.destination, args.verify_root, recovered_passphrase)
                    recovered_passphrase = None
                    print(f"Restore verification passed at {args.verify_root}.")
            else:
                result = verify_backup(args.backup, args.restore_root, passphrase)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, RuntimeError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Migration stopped: {error}\n")


if __name__ == "__main__":
    main()
