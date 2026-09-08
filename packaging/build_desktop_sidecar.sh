#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_dir=$(dirname -- "$script_dir")
python_bin=${SCANNER_PACKAGING_PYTHON:-"$project_dir/.venv313/bin/python"}

if [ ! -x "$python_bin" ]; then
  echo "Packaging Python was not found at $python_bin" >&2
  echo "Set SCANNER_PACKAGING_PYTHON to a Python environment with packaging/requirements.txt installed." >&2
  exit 1
fi

if ! "$python_bin" -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller is not installed for $python_bin" >&2
  echo "Run: $python_bin -m pip install -r $project_dir/packaging/requirements.txt" >&2
  exit 1
fi

"$python_bin" -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$project_dir/ui/src-tauri/resources" \
  --workpath "$project_dir/packaging/build/pyinstaller" \
  "$project_dir/packaging/desktop_sidecar.spec"

echo "Desktop sidecar created at ui/src-tauri/resources/swing-scanner-sidecar"
