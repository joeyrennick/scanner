# Phase 0 Mac packaging verification

Verified on 2026-09-06 with macOS 26.5.2 (25F84), Apple Silicon, Rust 1.98.1,
Cargo 1.98.1, Python 3.13.14, and PyInstaller 6.22.2.

## Artifact and build

Application: `ui/src-tauri/target/release/bundle/macos/Swing Scanner.app`

The application occupies approximately 132 MB. Both its native host and
packaged sidecar are Mach-O arm64 executables. The complete PyInstaller
one-directory output is bundled under `Contents/Resources/sidecar`.

The first full Rust build failed because Tauri requires an application icon.
`ui/src-tauri/icons/icon.svg` is the source of the generated `icon.png` and
`icon.icns`, now explicitly included in `tauri.conf.json`. Cargo dependency
resolution is recorded in `ui/src-tauri/Cargo.lock`.

The sidecar and production frontend builds passed. After adding the icons,
`./node_modules/.bin/tauri build` completed the application bundle successfully.
The complete build entry point remains:

```bash
cd /Users/joe.rennick/scanner/ui
npm run desktop:build
```

This is a local development artifact. `codesign --verify --deep --strict`
does not pass for this unsigned bundle; Developer ID signing, notarization,
Gatekeeper acceptance on another Mac, and distribution are deferred to Phase 4.

## Phase 0 exit criteria

| Criterion | Observed evidence | Result |
| --- | --- | --- |
| Opens without Terminal or an external browser | Finder opened the `.app` through its ordinary application-open action. The native window rendered the readiness interface. | Pass |
| One host owns one backend child | Finder launch: host PID 11641, direct backend child PID 11648. Isolated launch: host PID 12661, one direct child PID 12668. | Pass |
| Quit leaves no orphaned backend | Normal macOS application termination removed both Finder-launched processes. The isolated run logged graceful Uvicorn shutdown, exited with status 0, and its child PID no longer existed. | Pass |
| No fixed development port | Finder launch listened on `127.0.0.1:59426`; isolated native launch selected `127.0.0.1:60168`. | Pass |
| Authenticated WebView request and unauthenticated rejection | Both native windows rendered “Packaged backend connected,” the actual backend PID, and dependency versions. An unauthenticated request to the Finder-launched backend returned HTTP 401. | Pass |
| Native-heavy dependency imports | The isolated packaged health response reported every required dependency, listed below. | Pass |
| Works with ports 5173 and 8000 occupied | The verification driver held listening sockets on both ports throughout the isolated app launch, WebView readiness, and quit. | Pass |
| Works without repository, external Python, or virtual environment | A copied bundle ran outside the repository under enforced filesystem restrictions denying those runtime dependencies; its WebView reached connected status. | Pass |

The native window content was inspected using the authorized macOS
accessibility interface, including the WebView heading and dependency list.
Automated screenshot capture was blocked by macOS Screen Recording permission;
no screenshot-based visual layout review is claimed.

## Isolated runtime check

The bundle was copied with `ditto` to
`/private/tmp/swing-scanner-phase0.biStA5/Swing Scanner.app`. Only the copied
application ran inside the verification sandbox. The development repository,
virtual environments, and Python installations were not renamed or modified.

The verification driver removed inherited `PYTHON*`, `VIRTUAL_ENV*`, and
`SCANNER_DESKTOP_*` overrides, set `PATH` to system utility directories, and
used a working directory outside the repository. It held ports 5173 and 8000
open and launched the copied native executable with `sandbox-exec` using:

```scheme
(version 1)
(allow default)
(deny file-read* file-write* (subpath "/Users/joe.rennick/scanner"))
(deny file-read* process-exec (subpath "/opt/homebrew"))
(deny file-read* process-exec (subpath "/usr/local"))
(deny file-read* process-exec (subpath "/Library/Frameworks/Python.framework"))
(deny file-read* process-exec (literal "/usr/bin/python3"))
(deny file-read* process-exec (subpath "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework"))
```

A control probe under the same profile failed to read the repository README
with “Operation not permitted,” confirming that the isolation was enforced.
The restriction on the whole repository also covers `.venv` and `.venv313`.
Bundled Python and native libraries remained available inside the copied app.

Before launching the native host, the driver separately exercised the copied
sidecar under the same isolation profile with a fresh in-memory test token:

- Authenticated health returned HTTP 200 with the expected process ID.
- Missing and incorrect tokens returned HTTP 401.
- Unauthenticated shutdown returned HTTP 401.
- `tauri://localhost` received the expected CORS response header; an untrusted
  origin received no allow-origin header.
- Authenticated shutdown returned HTTP 202 and the sidecar exited with status 0.

The native host then generated its own port and token. Its WebView displayed
connected status and all dependency versions. A normal macOS quit produced
graceful backend shutdown and no remaining child process. The test driver
released both occupied ports on completion.

Temporary verification helpers are in the same `/private/tmp` directory;
they are session artifacts and may be removed by macOS. The sandbox profile,
procedure, and observations above are the durable evidence.

## Dependency versions from the packaged runtime

| Dependency | Version |
| --- | --- |
| certifi | 2026.06.17 |
| lxml | 6.1.1.0 |
| matplotlib | 3.11.0 |
| NumPy | 2.5.0 |
| pandas | 3.0.3 |
| Pillow | 12.2.0 |
| Uvicorn | 0.50.0 |

## Automated checks

- `PYTHONPATH=src .venv313/bin/pytest tests/test_desktop_sidecar.py -q`:
  **3 passed**, one dependency deprecation warning.
- `npm test` in `ui`: **52 passed** across 10 test files.
- `npm run build` in `ui`: passed.
- `cargo fmt --check` in `ui/src-tauri`: passed.
- `git diff --check`: passed.

The full Python suite was not rerun in this continuation. Its recorded baseline
remains **239 passed, 1 skipped, 1 failed**. The existing failure is
`test_market_data_history_endpoint_returns_intraday_timestamps`, whose fixed
2026-08-28 fixture is removed by a relative one-day trim. It remains separate
from packaging verification.

## Next phase

Phase 1 has not started. Inventory mutable application data and create a
recoverable essential-data backup before changing filesystem paths or importing
data. The full scanner interface, Keychain, AI Analysis, iPhone companion,
PostgreSQL, and public distribution retain the order and boundaries in
`APPLE_APPLICATION_IMPLEMENTATION_PLAN.md`.
