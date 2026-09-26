"""Versioned business-record API; existing /api routes remain unchanged."""
from typing import Any
import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from scanner.config.paths import ApplicationPaths
from scanner.data.browser_records import BrowserRecordStore, RevisionConflict
from scanner.data.ownership import acquire_root
from scanner.migration.browser import COLLECTIONS

router = APIRouter(prefix="/api/v1/business-records")


class RecordMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: dict[str, Any]
    expected_revision: int = Field(ge=0, strict=True)


def _store():
    return BrowserRecordStore(ApplicationPaths.resolve().browser_database)


@router.get("/migration-status")
def migration_status():
    """Read-only, allowlisted import identity. Never initialize an empty store here."""
    paths = ApplicationPaths.resolve()
    ownership = acquire_root(paths.root)
    try:
        receipt_path = paths.data / "import-receipt.json"
        if not receipt_path.exists():
            return {"schema_version": 1, "imported": False}
        receipt = json.loads(receipt_path.read_text())
        counts = receipt["browser_counts"]
        if (receipt["version"] != 1 or receipt["active_store_imported"] is not True
                or not paths.browser_database.is_file() or set(counts) != COLLECTIONS
                or any(type(count) is not int or count < 0 for count in counts.values())
                or not isinstance(receipt["import_id"], str) or not receipt["import_id"]
                or not isinstance(receipt["browser_source"]["origin"], str)):
            raise ValueError("Unsupported import receipt")
        return {"schema_version": 1, "imported": True, "import_id": receipt["import_id"],
                "browser_origin": receipt["browser_source"]["origin"], "imported_counts": counts}
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise HTTPException(status_code=409, detail="Import receipt is unavailable or invalid; keep editing paused") from error
    finally:
        del ownership


@router.get("/{collection}")
def list_records(collection: str):
    try:
        return {"schema_version": 1, "collection": collection, "records": _store().list(collection)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{collection}/{record_id:path}")
def get_record(collection: str, record_id: str):
    try:
        return _store().get(collection, record_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.put("/{collection}/{record_id:path}")
def put_record(collection: str, record_id: str, request: RecordMutation):
    if request.record.get("id") != record_id:
        raise HTTPException(status_code=422, detail="Record ID does not match the request path")
    try:
        return _store().put(collection, request.record, request.expected_revision)
    except RevisionConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.delete("/{collection}/{record_id:path}")
def delete_record(collection: str, record_id: str, expected_revision: int = Query(ge=1)):
    try:
        return _store().delete(collection, record_id, expected_revision)
    except RevisionConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
