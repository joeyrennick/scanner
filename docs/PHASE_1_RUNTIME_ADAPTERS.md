# Phase 1 runtime and file contract

This is a tested browser/runtime foundation, not full native-app acceptance.

## Connection and capabilities

`GET /api/v1/runtime` returns schema version 1, supported API versions, the legacy
compatibility prefix, runtime mode, explicit feature flags, and resolved data,
cache, report, log and export paths. It does not create databases or return
credential values. Browser mode advertises scanner/business/file support. The
desktop proof requires its launch bearer and advertises only its lifecycle/runtime
features; it does not expose scanner routes, Keychain or native file dialogs.

`ui/src/platform/` defines the injectable `PlatformRuntime`, `FileActions`,
`FilePresenter` and desktop-host connection interfaces. API hooks, credential
controls and the business provider use the same injected API client. The desktop
host adapter validates an HTTP IPv4 loopback origin and holds the launch token in
the API closure, not React display state or localStorage. Tauri commands remain
in the host adapter; runtime detection stays in the bootstrap.

## File actions and compatibility

- `GET /api/v1/reports/{report_id}/download` downloads an existing report ID.
- `GET /api/v1/reports/{report_id}/view` previews a PDF only.
- `GET /api/v1/jobs/{job_id}/outputs/{output_name}/download` resolves a known
  output of that in-memory job. There is no arbitrary client path argument.
- Report IDs retain the existing URL-safe base64 encoding of a report-root-relative
  name. Clients treat them as opaque and receive them from report metadata.
  They survive working-directory/report-root changes, but not a report rename.
- `/api/reports` metadata and generation routes remain the compatibility API;
  their path fields are diagnostic/legacy fields, not input to new file actions.
  Legacy download routes accept old absolute IDs only inside the report root.
- Supported file extensions are PDF, HTML, CSV and LOG. Only reports, logs and
  managed temporary exports are eligible. JSON snapshots, database/key files,
  symlinks and nonregular files are not downloadable. Relative repository job
  paths and outputs outside these roots are refused without a cwd fallback.
- Directory/file descriptors are opened with no-follow semantics. A path change
  after opening cannot redirect the response. Growing files are streamed only
  through their initial size. Responses are no-store/nosniff and sandboxed.

The API client fetches bytes with the configured Authorization header and refuses
redirects. It decodes/sanitizes the response filename. Tokens never appear in a
download/preview URL. The browser presenter downloads a blob without navigating
away; PDF preview reserves a window during the click, removes its opener, then
loads the fetched blob. Errors close the preview and remain visible to the user.
Local CSV/recovery-export/draft files also use the presenter. Native file handling
requires a native presenter; there is no implicit browser fallback in the proof.

## Tests and remaining acceptance

Run `PYTHONPATH=src .venv313/bin/python -m pytest -q` from the repository, and
`npm test` / `npm run build` from `ui`. The frontend real-API test uses
`.venv313/bin/python` (or `SCANNER_TEST_PYTHON`) with all roots in a temporary
directory and no provider calls. Coverage includes file bytes/filenames,
authenticated transport, injected connections, runtime flags, legacy consumers,
traversal/symlink/path-replacement rejection and database restart persistence.

Still open: configuration/setup, full installed-app/path-independence checks,
native save/open actions, Keychain, production CORS/CSP/authentication, durable
job identities and full Phase 2 API/retry contracts. This contract alone does
not pass those gates.
