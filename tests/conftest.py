"""All test defaults are isolated before application modules are imported."""
import os
from pathlib import Path
import tempfile

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    workspace = tempfile.TemporaryDirectory(prefix="scanner-tests-")
    config._scanner_workspace = workspace
    root = Path(workspace.name)
    overrides = {
        "SCANNER_DATA_ROOT": str(root / "application"),
        "SCANNER_CACHE_ROOT": str(root / "cache"),
        "SCANNER_REPORT_ROOT": str(root / "application/reports"),
        "SCANNER_LOG_ROOT": str(root / "logs"),
        "MPLCONFIGDIR": str(root / "matplotlib"),
    }
    config._scanner_previous_environment = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)


def pytest_unconfigure(config):
    for key, value in getattr(config, "_scanner_previous_environment", {}).items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    workspace = getattr(config, "_scanner_workspace", None)
    if workspace is not None:
        workspace.cleanup()
