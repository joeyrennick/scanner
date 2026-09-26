# Phase 1 application configuration and SEC contact setup

The browser Settings page now provides **SEC Contact Setup**. The user explicitly
supplies an application/organization name and contact email. It is not a password,
API key, account registration, or SEC login. Saving is local and makes no provider
request. Subsequent SEC provider instances send that identity in the User-Agent
header. The form links to the SEC's [declared request header guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).

No personal developer identity is prefilled. `Swing Scanner` is only the suggested
application name; the contact email starts empty. Provider credentials and backup
passwords remain separate and are never read or changed by this setup path.

## Storage and precedence

`ApplicationPaths.application_settings` resolves to:

`<SCANNER_DATA_ROOT>/configuration/application-settings.json`

This is a version-1 document containing a revision and a nullable `sec_identity`
object with `application_name` and `contact_email`. It is ordinary private local
configuration, **not encrypted credential storage**. Newly written files use mode
0600. Existing historical `configuration/scanner-settings.json` is an archived
backup-process snapshot; it is never applied as live configuration. No source
paths, historical personal identities, or archived settings are auto-imported.

SEC identity precedence at provider construction:

1. An explicitly passed code-level `user_agent` (the optional
   `ScannerSettings.sec_user_agent` override).
2. `SEC_USER_AGENT` from the backend/CLI launcher environment.
3. The saved application contact.
4. No identity; SEC network requests are refused with setup instructions.

An invalid or blank launcher override is an error, not permission to fall back to
a different saved identity. Setup displays that error without echoing the invalid
header. Changing a launcher environment requires a backend restart. Changing
saved setup does not: new providers load it; existing provider instances retain
their original identity. The compatibility `/api/settings` view and future legacy
backup-process settings snapshots report the effective identity. Provider code
overrides are not a user-editable setting and are absent in the normal API runtime.

This increment does not turn the other `ScannerSettings` fields into editable
persisted configuration. Existing environment/path overrides remain supported.

## API, consistency, and failure handling

- `GET /api/v1/setup`: configuration revision, effective SEC identity/source,
  configured flag, and any launcher-override error. No credentials or provider
  network calls. A missing configuration stays missing; GET does not create it.
- `PUT /api/v1/setup`: strict `{expected_revision, sec_identity}`. Unknown fields,
  invalid email/name/header characters, and coerced revision types are rejected.
  `null` removes the saved identity while retaining an incremented revision.
  The current browser form supports creating/updating contact details.
- Responses containing setup use `Cache-Control: no-store`. These routes use the
  existing browser API security model; production desktop authentication/CORS/CSP
  hardening is still Phase 2. The desktop proof does not expose setup routes or
  claim a full native Settings screen.
- Saves join the existing root ownership lease and serialize within the process.
  Stale revisions return 409. Descriptor-relative no-follow reads/writes reject
  symlink configuration paths and nonregular files. Writes fsync a private new
  file, atomically replace the configuration, and fsync the directory. Unsupported,
  oversized, duplicate-field, or malformed existing documents are preserved and
  block replacement rather than being treated as empty.
- A lost response is ambiguous: the form retains the draft and disables another
  save until **Discard draft and reload saved setup** is explicitly selected.
  It never retries mutations automatically or saves contact details to browser
  storage. Dirty/pending forms warn on browser unload; window focus does not
  replace a draft. Reload does not claim an earlier unconfirmed write succeeded.
- An interrupted write before replacement leaves the previous configuration;
  an interrupted process may leave an unused `application-settings-*.tmp` file.
  Such files are not read as configuration. After replacement, reload determines
  which revision is present; do not delete the live file or reset its revision.

Existing recovery backups predate new setup and later business edits; they are
not current snapshots of this application configuration. No backups are rewritten
by setup. Post-import ongoing backup/upgrade tooling remains separate work.

## Verification and remaining gates

Tests cover a new process/different working directory reading saved identity,
the real TypeScript client talking to the Python API across restart, precedence,
provider instance snapshots and mocked request headers, missing/invalid identity,
read-only behavior, legacy archive preservation, thread/process ownership,
conflicts/remove-recreate revisions, invalid input, symlinks/FIFOs, and failed
atomic replacement. UI tests cover explicit save, blank email, override notices,
no localStorage writes, unsupported schema, loading failure, retained drafts,
unload warning, and conflict/ambiguous-response reload.

Tests use temporary path roots and no live market/SEC provider requests. The user
still needs to choose and save their actual contact in Settings. This is not SEC
server acceptance testing. Installed/no-repository/relaunch Phase 1 validation,
remaining path independence, and full native setup integration remain pending.
