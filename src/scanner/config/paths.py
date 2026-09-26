"""One platform-resolved path contract; resolution never creates user files."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from platformdirs import user_cache_dir, user_data_dir, user_log_dir
from scanner.migration.ownership import root_identity

APP_NAME = "Swing Scanner"


def _inside(path: Path, directory: Path) -> bool:
    candidate, parent = root_identity(path), root_identity(directory)
    return candidate == parent or candidate.startswith(parent.rstrip("/") + "/")


def _path(name: str, default: str | Path) -> Path:
    result = Path(os.environ.get(name, str(default))).expanduser()
    if not result.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    return result.resolve()


@dataclass(frozen=True)
class ApplicationPaths:
    root: Path
    cache: Path
    reports: Path
    logs: Path

    @classmethod
    def resolve(cls) -> ApplicationPaths:
        root = _path("SCANNER_DATA_ROOT", user_data_dir(APP_NAME, appauthor=False))
        paths = cls(
            root=root,
            cache=_path("SCANNER_CACHE_ROOT", user_cache_dir(APP_NAME, appauthor=False)),
            reports=_path("SCANNER_REPORT_ROOT", root / "reports"),
            logs=_path("SCANNER_LOG_ROOT", user_log_dir(APP_NAME, appauthor=False)),
        )
        # Cache eviction must not contain or sit inside durable storage.
        for durable in (paths.root, paths.reports):
            if _inside(durable, paths.cache) or _inside(paths.cache, durable):
                raise ValueError("Cache and durable data directories must be separate")
        return paths

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def database(self) -> Path:
        return self.data / "scanner.sqlite"

    @property
    def browser_database(self) -> Path:
        return self.data / "browser-records.sqlite"

    @property
    def application_settings(self) -> Path:
        # The imported scanner-settings.json is an archive, never live configuration.
        return self.root / "configuration" / "application-settings.json"

    @property
    def credential_database(self) -> Path:
        return self.root / "credentials" / "legacy.sqlite"

    @property
    def market_database(self) -> Path:
        return self.cache / "market" / "market.sqlite"

    @property
    def latest_watchlist(self) -> Path:
        return self.reports / "watchlist.csv"

    @property
    def journal(self) -> Path:
        return self.data / "trade_journal.csv"

    @property
    def exports(self) -> Path:
        return self.cache / "exports"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    def ownership_root(self, path: str | Path) -> Path:
        candidate = Path(path).resolve()
        for directory in (self.root, self.cache, self.reports, self.logs):
            if _inside(candidate, directory):
                return self.root
        # Explicit legacy/test database overrides share ownership of their parent.
        return candidate.parent
