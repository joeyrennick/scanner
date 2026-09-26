from __future__ import annotations

import hashlib
import json
import math
import re
from urllib.parse import urlsplit

MAX_BROWSER_BYTES = 5 * 1024 * 1024
COLLECTIONS = {"plannedTrades", "candidateEdits", "valuationAssumptions", "browserSettings"}
SETTINGS_FIELDS = {
    "swing-scanner.recommendation-settings": {"rewardRiskMultiple": "number", "suggestedHoldDays": "number", "stopMethod": "string", "atrPeriod": "number", "riskPerTradePercent": "number", "defaultExportScope": "string", "includeAdjustedChecklistValues": "boolean"},
    "swing-scanner.cache-settings": {"historyPeriod": "string", "staleAfterDays": "number", "batchSize": "number", "batchDelayMs": "number", "stopOnRateLimit": "boolean"},
    "swing-scanner.market-data-settings.v2": {"primaryProvider": "string", "backupProvider": "string", "requestMode": "string", "maxProviderBatches": "number", "testSymbol": "string"},
    "swing-scanner.appearance-settings": {"density": "string", "tablePageSize": "number", "defaultChartRange": "string", "rememberChartResize": "boolean"},
    "swing-scanner.display-settings": {"minStopDistancePercent": "number", "minFiveDayRange": "number"},
}


def _text(value, limit=2000, nonempty=False):
    if not isinstance(value, str) or len(value) > limit or (nonempty and not value.strip()):
        raise ValueError("Invalid browser record text")


def validate_browser_export(raw: bytes) -> dict:
    try:
        return _validate_browser_export(raw)
    except (KeyError, TypeError, OverflowError, UnicodeError, json.JSONDecodeError):
        raise ValueError("Malformed browser export; original records must be retained") from None


def _validate_browser_export(raw: bytes) -> dict:
    if len(raw) > MAX_BROWSER_BYTES * 2:
        raise ValueError("Browser export is too large")
    envelope = json.loads(raw)
    if (not isinstance(envelope, dict) or set(envelope) != {"format", "version", "payloadJson", "sha256"}
            or envelope["format"] != "swing-scanner.browser-export"
            or type(envelope["version"]) is not int or envelope["version"] != 1):
        raise ValueError("Unsupported browser export format")
    payload_text = envelope["payloadJson"]
    _text(payload_text, MAX_BROWSER_BYTES)
    payload_bytes = payload_text.encode("utf-8")
    if len(payload_bytes) > MAX_BROWSER_BYTES or hashlib.sha256(payload_bytes).hexdigest() != envelope["sha256"]:
        raise ValueError("Browser export checksum mismatch")
    payload = json.loads(payload_text)
    if not isinstance(payload, dict) or set(payload) != {"source", "counts", "collections"}:
        raise ValueError("Invalid browser export payload")
    source = payload["source"]
    if not isinstance(source, dict) or set(source) != {"origin", "exportId", "exportedAt", "writePauseConfirmed"}:
        raise ValueError("Invalid browser source")
    for field in ("origin", "exportId", "exportedAt"):
        _text(source[field], 256, nonempty=True)
    origin = urlsplit(source["origin"])
    if (origin.scheme not in {"http", "https"} or not origin.hostname or origin.username
            or origin.password or origin.path or origin.query or origin.fragment
            or source["writePauseConfirmed"] is not True):
        raise ValueError("Browser export must identify its original origin and write pause")
    collections = payload["collections"]
    counts = payload["counts"]
    if (not isinstance(collections, dict) or set(collections) != COLLECTIONS
            or not isinstance(counts, dict) or set(counts) != COLLECTIONS):
        raise ValueError("Unsupported browser collections")
    for name, rows in collections.items():
        if (not isinstance(rows, list) or len(rows) > 10000 or type(counts[name]) is not int
                or len(rows) != counts[name]):
            raise ValueError("Browser record count mismatch")
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Invalid browser record")
            _text(row.get("id"), 128, nonempty=True)
            if row["id"] in seen:
                raise ValueError("Duplicate browser record ID")
            seen.add(row["id"])
            if name == "browserSettings":
                if (set(row) != {"id", "values"} or row["id"] not in SETTINGS_FIELDS
                        or not isinstance(row["values"], dict)
                        or set(row["values"]) - SETTINGS_FIELDS[row["id"]].keys()):
                    raise ValueError("Unsupported browser setting")
                for field, value in row["values"].items():
                    kind = SETTINGS_FIELDS[row["id"]][field]
                    if kind == "string":
                        _text(value, 256)
                    elif kind == "boolean" and type(value) is not bool:
                        raise ValueError("Invalid boolean browser setting")
                    elif kind == "number" and (type(value) not in (int, float) or not math.isfinite(value)):
                        raise ValueError("Invalid numeric browser setting")
            elif name == "valuationAssumptions":
                if set(row) != {"id", "assumptions"} or not isinstance(row["assumptions"], dict):
                    raise ValueError("Invalid valuation record")
                for key, value in row["assumptions"].items():
                    if (not re.fullmatch(r"[a-z_]{1,80}", key) or type(value) not in (int, float)
                            or not math.isfinite(value)):
                        raise ValueError("Invalid valuation assumption")
            else:
                expected = {"id", "entry", "stop", "target"}
                if name == "plannedTrades":
                    expected |= {"ticker", "strategy", "plannedAt", "status"}
                if set(row) != expected:
                    raise ValueError("Unknown browser record fields")
                for field in expected:
                    _text(row[field])
                if name == "plannedTrades" and row["status"] != "planned":
                    raise ValueError("Unsupported Planned Trade status")
                if name == "plannedTrades":
                    _text(row["ticker"], 128, nonempty=True)
                    _text(row["plannedAt"], 64)
    return payload
