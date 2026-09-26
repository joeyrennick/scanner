# Swing Scanner Session Handoff

- Last updated: 2026-09-26
- Working directory: `/Users/joe.rennick/scanner`
- Branch: `main`
- Current implementation base: `f9ef479 Add Mac packaging proof and audited Apple application plan`
- Current session: Phase 1 recovery tooling and runtime foundations are uncommitted; do not commit or push
  without the user's instruction. `.idea/` remains unrelated local metadata.
- Pre-publication HEAD: `f9e2a88 Document deferred PostgreSQL setup`
- Publication scope: the user requested committing and pushing the completed
  Phase 0 proof, audited plan, and handoff on 2026-09-07. Exclude `.idea/` and
  generated build/resource output. Use `git status` and `git log` for the current
  commit and remote state; the working-tree inventory below predates publication.
- Codex CLI: `0.153.4`

### Latest continuation — contact setup verified; desktop bundle rebuilt (2026-09-26)

The prior contact state was unknown to the user. A read-only GET to
`/api/v1/setup` confirmed saved revision **1**, application name `Swing Scanner`,
and a configured SEC identity (`source: saved`). Do not copy the email into
additional logs or handoffs. The local API was briefly started on `127.0.0.1:8000`
for the GET-only check (tool session **98384**, PID **32887**) and stopped cleanly
before the desktop launch. It no longer owns the active data root. Vite is not
running. No jobs were submitted through that server.

`npm run desktop:build` completed successfully. The generated Apple Silicon app
is at `ui/src-tauri/target/release/bundle/macos/Swing Scanner.app` (132 MB). It
was moved from the repository root to `/Users/joe.rennick/Swing Scanner.app` at
the user's direction. An earlier attempt to place it in `/Applications` failed
with `ditto: ... Permission denied`; no files were written there. The development
backend was stopped cleanly before the move. Launch from the home-directory copy
was requested with macOS `open`, which exited successfully. The rendered window
and backend readiness were not independently inspected. Installed/no-repository/
relaunch acceptance remains incomplete. No application source changes were made
in this continuation. The native app still exposes only the Phase 0 proof.

Static path review found no implicit repository-relative `output/` defaults in
runtime `src`; remaining relative paths are explicit CLI inputs, legacy
compatibility overrides, or test/migration fixtures. No tests were run. No commit
or push was made; preserve `.idea/` and all existing uncommitted work.

## Start here in the next session

### Previous checkpoint — application/SEC contact setup ready (2026-09-13; superseded 2026-09-26)

The next Phase 1 increment is implemented and running in the development browser.
Settings now has **SEC Contact Setup**. The user must still choose and save their
contact email; no identity has been selected for them. Live GET reports revision
0, `sec_configured: false`, source `missing`, and no error. Do not ask for an SEC,
Massive, Mac, or recovery password: this is application name plus contact email,
sent in SEC request headers only when requesting data. The form explains this and
links to official SEC guidance. Suggested application name: **Swing Scanner**.

Implementation (uncommitted):

- `config/application.py` owns a strict version-1, revision-checked configuration
  at `configuration/application-settings.json`, resolved by `ApplicationPaths`.
  Reads create nothing. Writes share root ownership, serialize in-process, and
  use private, fsynced, atomic descriptor-relative replacement. Unsupported or
  corrupt documents, symlinks, FIFOs, duplicate fields and stale saves are refused.
- `/api/v1/setup` GET/PUT exposes saved and effective SEC configuration, never
  credentials. The archived `configuration/scanner-settings.json` is not applied
  live. Existing backups are not changed or made current by this feature.
- SEC providers resolve explicit code override > launcher `SEC_USER_AGENT` > saved
  contact > missing. Invalid/blank launcher overrides block silent fallback and
  are explained in Settings. Saved changes apply to new provider instances without
  restarting; existing instances retain their original identity. Missing identity
  blocks SEC network requests. `/api/settings` and future legacy backup-process
  settings snapshots report the effective identity.
- The typed frontend uses the injected API connection. No localStorage contact
  persistence or automatic save/retry. Error/ambiguous writes retain the draft
  and require explicit discard/reload before another save. Loading errors do not
  enable a blank replacement form. Dirty/pending forms warn on browser unload.

Verification: **402 Python tests passed, 1 skipped**, one existing dependency
warning; **122 frontend tests and production build passed**. Tests include process
restart/different cwd, the real TS/Python setup API across restart, ownership,
precedence, concurrent revisions, atomic failure, malformed configuration,
provider header snapshots (mocked), and form failure/draft behavior. No live SEC
or market-provider requests, credential values, or real setup writes were used.
See `docs/PHASE_1_APPLICATION_SETUP.md` for the contract and remaining scope.

The user confirmed all jobs were stopped and would stay stopped for the restart.
Old backend PID 53818/session 81859 exited cleanly. New backend PID **74108**, tool
PTY session **64100**, serves port **8000**; Vite PID **87647** serves **5173**.
Recheck these before acting next session. GET-only live checks across restart
confirmed unchanged record envelope hashes for **8 Planned Trades / 37 candidate
edits / 48 assumptions / 4 settings groups**. Setup returns 200 and no-store.
No original data, import receipt, backup, or credential files were changed.

User-facing next step: refresh `http://127.0.0.1:5173/settings`, find **SEC Contact
Setup**, keep **Swing Scanner** as the name (or choose their organization), enter
their own contact email, and click **Save SEC contact**. No restart is needed after
saving. Normal browser use can resume. Do not replay import/recovery steps.

After contact is saved: remaining path independence and installed/no-repository/
relaunch Phase 1 acceptance. Other settings have not all become persisted/editable;
the native app is still the Phase 0 proof, with no new build/install this increment.
Full native integration, Keychain, dialogs and production security remain Phase 2.
No commit or push. Preserve unrelated `.idea/` metadata.

### Previous checkpoint — browser switch confirmed; runtime/file adapters (2026-09-13)

The user confirmed completing the migration-page check and **Resume with imported
database**. Do not ask them to repeat backup/import/password recovery or assume
the browser is still paused. The previous backend log also showed the subsequent
Journal/watchlist reads. The user confirmed no jobs were running and was asked
not to start new jobs while the tested backend update was restarted.

Implemented in this increment (uncommitted):

- `ui/src/platform/` provides a typed, injectable runtime, API connection and file
  actions/presenter boundary. Existing API hooks and the business-record provider
  use the injected client. Tauri IPC is confined to the host adapter/bootstrap;
  the proof screen no longer holds the bearer token in React display state.
- Browser report/PDF/job downloads and local CSV/export/draft downloads use the
  file adapter. Remote downloads use headers, never tokens in links. PDF preview
  reserves a window before fetching, disconnects its opener, and closes on failure.
  Failures are visible. URLs are released after use; non-PDF inline preview is
  refused. Native dialogs/preview are explicitly unavailable in the proof.
- `/api/v1/runtime` advertises implemented capabilities, API/compatibility
  versions, and backend-resolved paths without creating stores or exposing
  credentials. Settings has an **Application Runtime** panel. The authenticated
  desktop proof advertises its limited capabilities, not the full scanner.
- `/api/v1/reports/{id}/download|view` and
  `/api/v1/jobs/{job_id}/outputs/{name}/download` use IDs/server-known outputs.
  Files are restricted to supported report/log/export extensions and managed
  roots. Descriptor-relative, no-follow opens reject symlinks, traversal, keys,
  databases, directories and FIFOs, and survive path replacement after opening.
  Downloads use no-store/nosniff/sandbox headers; inline viewing is PDF-only.
- Existing report IDs and `/api` consumers are retained as compatibility paths.
  Legacy absolute report IDs are accepted only by legacy routes inside the report
  root. Old relative job output paths and outputs outside the managed roots are
  not downloadable; the UI no longer constructs report IDs from those paths.

Verification: **368 Python tests passed, 1 skipped**, one existing dependency
warning; **110 frontend tests and production build passed**. This includes the
TypeScript runtime/file adapter consuming real Python responses in an isolated
test directory, PDF bytes/Unicode filenames, database process restart, injected
API hooks, desktop endpoint validation, pause enforcement and file-access attacks.
No new native bundle/install was performed. The old packaged app is still Phase 0.

The development backend was cleanly restarted with user-approved permissions:
PID **53818**, tool PTY session **81859**, port **8000**. Existing Vite PID **87647**
serves port **5173**. Recheck processes before acting in the next session. The
backend owns the active data root; maintenance must not run alongside it.
Live API checks across that restart matched every business-record envelope hash:
8 Planned Trades / 37 candidate edits / 48 assumptions / 4 settings groups.
The runtime endpoint reports the expected paths/capabilities. Two saved reports
are listed; the existing 36,633-byte PDF downloaded exactly like its disk file
(SHA-256 `b8921c774aceaa624d0fee0b400312d11af0015eb0305f34a936e74c72a3c871`).
Checks used GETs only, no provider calls or credential reads, and no original
data/backup changes. The user can refresh the browser and resume normal use.

Next: configuration/setup (including an explicitly supplied SEC contact identity),
remaining path independence and packaged/relaunch/no-repository Phase 1 acceptance.
Full native scanner integration, native file dialogs, host-owned Keychain and
production authentication/CORS/CSP remain Phase 2 work. The runtime panel is not
a claim that those features or all Phase 1 exit criteria are complete. No commit
or push; preserve unrelated `.idea/` metadata.

### Previous checkpoint — browser UI uses imported database (2026-09-13)

The four browser business collections now use `/api/v1/business-records` throughout
Journal, Candidates, Fundamentals, and Settings. Original browser business keys
are retained unchanged. New versioned chart/fundamentals preference keys contain
only display/navigation state; settings groups are read from the imported store.

The shared frontend provider loads all collections before mounting application
pages. Saves are serialized with expected revisions, including delete/re-create
tombstones and URL-encoded record IDs. Pending saves have a visible banner and
close-window warning. Conflicts or ambiguous failures stop further writes, retain
the draft in memory, and offer a draft download plus explicit discard/reload.
There are no automatic mutation retries or localStorage business-data fallbacks.
Operation-ID retry receipts remain Phase 2 work; this increment does not claim them.

The migration page now checks the completed import identity, original browser
origin, and exact records before allowing the initial database switch. Resume
rechecks rather than trusting an earlier button click. Its versioned source marker
stores only import identity/origin and an original-data digest. Later legitimate
database edits do not re-import the old browser copy; changes to that copy stop
resumption for review. The original export is labeled archival, not a backup of
new database edits. The status endpoint exposes no credentials or private receipt
metadata and does not initialize a missing database.

Verification: **350 Python tests passed, 1 skipped** (one existing dependency
warning); **87 frontend tests and production build passed**. New tests include
all four rendered pages, StrictMode/load gating, preservation of legacy keys,
rapid edits, conflict/failure handling, tombstones, migration reconciliation,
and the TypeScript store against the real Python API/SQLite across process restart.
The frontend integration test uses `.venv313/bin/python`, overridable with
`SCANNER_TEST_PYTHON`; all its roots are temporary and no provider is called.

Read-only live checks still reconcile import `22085cefcf09428e9e68186e9fcfeb6e`
and the fresh export exactly: **8 / 37 / 48 / 4** browser records, 13 saved scans /
2,230 results, 1 watchlist / 7 items. All four live API GET collections through
the Vite proxy also match the export. No production business edits, provider
requests, password-manager access, repeat import, or backup changes were made.

The local development backend was started on `127.0.0.1:8000`; the existing Vite
server serves `http://127.0.0.1:5173`. Recheck process/port state next session;
the backend owns the active root, so maintenance/import must not run alongside it.
The user-facing next step is the **original browser** migration page at
`http://127.0.0.1:5173/migration`: close other Scanner tabs, confirm, choose
**Check imported database records**, then **Resume with imported database** if
the check passes. No password is needed. We have NOT removed the user's browser
pause or observed their final browser switch; do not claim that step completed.

Phase 1 is still open: finish path/file/runtime adapters, configuration/setup,
and packaged/relaunch/no-repository acceptance. The native app still shows the
Phase 0 proof screen and was not rebuilt. Nonempty-store replacement/upgrades
remain unsupported. No commit/push; preserve unrelated `.idea/` metadata.

### Previous checkpoint — real import completed and reconciled (2026-09-13)

The user completed the new import runner. Independent read-only checks under
ownership verified the active receipt and reconciled the exact imported records:

- Import ID: `22085cefcf09428e9e68186e9fcfeb6e`.
- Imported at: `2026-09-14T01:25:46.881544+00:00` (September 13, 6:25 PM PDT).
- Backup ID: `2d2cf0e78c1a4434b537d758d4f947cc`.
- Active root: `~/Library/Application Support/Swing Scanner`.
- Saved scans: 13 / 2,230 result rows; watchlists: 1 / 7 items.
- Browser records: 8 Planned Trades, 37 candidate edits, 48 valuation-assumption
  records, 4 settings groups; exact records match the browser export.
- Business schema/row hashes reconcile, saved CSV/PDF hashes match, and one
  credential decrypts using the imported matching local key (verified in memory;
  no value printed and no provider calls made).
- No pending-import gate or activation journal remains. Source business data and
  durable files remain unchanged; both backups are preserved and verified intact.

**The live first import is complete. Do not rerun backup/import or request another
recovery password as the next step.** Phase 1 itself is not yet complete. Keep
browser editing paused: the current UI still uses its old business localStorage.
Next implementation work is wiring the browser/desktop UI to the new business
record API, preserving old localStorage/export data, then completing adapters,
configuration and packaged/relaunch/no-repository acceptance. The native app still
shows the Phase 0 proof screen; an imported store alone is not that acceptance.

Latest regression evidence remains 349 Python tests passed / 1 skipped, with one
existing dependency warning; previous frontend evidence is 58 tests/build passing.
No new code changes or native rebuild were needed to verify the real import.

### Prior checkpoint — replacement backup verified and selected

The replacement backup succeeded, and the user independently retrieved and
re-entered its saved password to verify recovery:

- Backup: `~/Library/Application Support/Swing Scanner/backups/phase1-2026-09-12-new-passphrase`.
- Isolated restore: `/private/tmp/scanner-phase1-restore-2026-09-12-new-passphrase`.
- Backup ID: `2d2cf0e78c1a4434b537d758d4f947cc`.
- Verified at: `2026-09-12T23:47:45.520088+00:00`.
- Six files, 13 scans / 2,230 result rows, 1 watchlist / 7 items, browser counts
  8 / 37 / 48 / 4, and one credential reconciled. Files/evidence and original
  source records were independently checked; both backups remain intact.

The new `select-verified-backup` maintenance command reassociated the unused
destination's pending gate with this new backup under OS ownership, preserving
the previous gate at
`~/Library/Application Support/.scanner-ownership/99c52efe458f49995d8ea04f7c08bed83a23731973b8d72a7becb046ac744d5c/history/3ba1c35f545d4fcd803b1bfad1d04c99-prior-pending-import.json`.
It checks verification evidence, source reconciliation, expected prior backup ID,
and unused slots before atomic replacement. Nine new selection tests pass; full
Python results are **349 passed, 1 skipped**, one existing dependency warning.
Previous frontend evidence remains 58 tests/build passing; no frontend or native
bundle changes were made in this increment.

The user explicitly said to continue. The NEW import runner was syntax-checked
and opened in Terminal:
`/private/tmp/scanner-phase1-verified-import.sBn26i/Import Verified Scanner Data.command`.
Use this runner, not either older import/backup runner. It previews the selected
new backup, asks for `IMPORT`, and then prompts once for the SAME password that
passed verification. The password is the Password field in the user's saved
entry titled `Scanner backup recovery - 2026-09-12 NEW`, not that title, its
username or website label. Never ask for the password in chat or read their
password manager. The user is currently asking how to retrieve the saved value.

Last on-disk check: no import receipt, no activation journal, pending-import
guard still present. Import completion remains **unverified/not yet observed**.
Check the actual receipt and reconciliation after local confirmation; do not
infer import success merely because Terminal opened. Keep browser editing paused
even after import until the UI is connected to the new business-record API.

### Earlier recovery checkpoint (superseded by the successful replacement above)

The user said they forgot the backup recovery phrase while the next import
increment was being prepared. **Do not attempt the live import or open the
prepared import runner.** No active data has been imported and the pending gate
remains intact. The original source was checked again read-only: 13 scans,
2,230 result rows, and the stored credential still decrypts with its existing
original local key. No key was replaced and no provider request was made.

The forgotten phrase cannot be retrieved from the encrypted recovery archive.
If it is not saved in the user's password manager, the safe next path is a new
coordinated backup and isolated restore using a new, separately saved phrase;
retain the old backup. After the new exercise passes, explicitly associate the
unused destination's pending-import gate with the newly verified backup under
ownership. Do not simply delete the guard or overwrite the old backup.

The user has now approved preparing the replacement backup. Prepared runner:
`/private/tmp/scanner-phase1-new-backup.0AYnjU/Create New Scanner Backup.command`.
It targets NEW backup
`~/Library/Application Support/Swing Scanner/backups/phase1-2026-09-12-new-passphrase`
and NEW isolated restore
`/private/tmp/scanner-phase1-restore-2026-09-12-new-passphrase`. It requires `READY`
confirmation that browser editing stayed paused and the new phrase is already
saved separately, then the existing CLI's three hidden passphrase prompts.
It performs backup/verification only, not import or pending-gate reassociation.
The new runner passed shell syntax checking and was opened in Terminal; all
29 backup/migration tests pass. Local prompt completion has not been verified.
The old six-file backup was rehashed and source business digests rechecked before
preparation; both remain unchanged. Both new destinations were unused. Completion
still requires successful local entry and fresh on-disk verification evidence;
do not infer success merely because the runner is prepared or Terminal opens.

The user created/saved a NEW recovery password, then supplied a fresh browser
export while checking the pause state:
`/Users/joe.rennick/Downloads/scanner-browser-export-2026-09-12T23-41-41-262Z.json`.
It validates (format/digest/counts), identifies the same original origin
`http://127.0.0.1:5173`, export ID `b83655b0-1fbc-44a4-ad0e-975b5a8a43ef`, captured
at `2026-09-12T23:41:41.259Z`, and confirms `writePauseConfirmed: true`. All four
business collections match the earlier export exactly: 8 Planned Trades,
37 candidate edits, 48 valuation-assumption records and 4 settings groups.
The original source-holder check passed again. Neither new backup/restore path
nor an active import receipt existed at this check. Because the records match,
the already-running Terminal backup runner can safely keep using its original
export input. Do not edit a script in place while its shell is waiting for input;
no runner restart or additional browser export is needed unless records change.
The fresh export is preserved as additional pause/reconciliation evidence. The
new phrase is entered only at the runner's hidden prompts, never through chat.

Implemented and tested in this increment (uncommitted):

- `migration/importer.py`: preview and idempotent first import from a verified
  backup, original-source reconciliation, isolated staging, recovered credentials,
  version-1 business/credential stores, exact browser record reconciliation and
  an import receipt. Existing destination slots are refused, not overwritten;
  replacement/upgrade of a nonempty active store is still unsupported.
- `migration/activation.py` and `files.py`: durable external activation journal,
  fixed data/report/credential/configuration slots, pre-commit rollback and
  post-commit completion under the OS lock. Startup recovers before opening stores.
  Failed stages and old gates/journals are retained; companion pairing is reset.
- `data/browser_records.py`, `data/schema.py`, and `/api/v1/business-records`:
  persistent browser records, schema identities, revision conflicts and delete
  tombstones. Existing browser consumers are preserved, but **the UI still uses
  its old business localStorage; keep it paused until API integration is complete**.
- CLI commands: `preview-import`, `import`, `recover-activation`. Import prints a
  preview, requires local `IMPORT` confirmation and a hidden saved-passphrase
  prompt. All four `SCANNER_*_ROOT` overrides select an isolated layout; first
  import currently requires reports at `<root>/reports`.
- Full Python suite: **340 passed, 1 skipped**, one existing dependency warning.
  **58 frontend tests** and frontend build pass. Tests force process death at
  eight activation boundaries, interrupt recovery itself, reject tampered partial
  generations and verify unchanged source data, repeat-import no-op, and cache
  eviction without losing imported records/reports. No native bundle rebuild.
- Real backup preview passed for backup `21177866cdb84b968fc65b590cf9fbad`, but
  real import has not run. A runner was prepared and syntax-checked at
  `/private/tmp/scanner-phase1-import.6LlYjN/Import Scanner Data.command`; it was
  **not opened**, and it targets the old phrase-protected archive.

The earlier implementation checkpoint follows for context; the latest status
above supersedes its pending staged-import implementation and test totals.

**Phase 0 — Mac packaging proof of concept is complete**, with every exit
criterion verified on 2026-09-06. **Phase 1 — Filesystem and configuration
readiness is now in progress**, beginning 2026-09-11. Read
`docs/PHASE_1_DATA_MIGRATION.md` for the current inventory and recovery procedure.

Completed preparation this session:

- Read-only inventory found 13 saved scans, 2,230 result rows, 1 watchlist with
  7 items, 1 saved PDF, and 1 encrypted credential in the mixed legacy database.
- Added a standalone `/migration` browser page and Settings link. It pauses
  updated browser tabs and exports Planned Trades, candidate trade levels,
  valuation assumptions and typed application settings with counts and digests.
  Original browser data remains intact, including malformed input.
- Added `scanner.migration` inventory, backup and isolated-restore CLI commands.
  Backup uses SQLite snapshots, excludes caches from essential data, and protects
  the credential database projection and matching key in a separate encrypted
  archive. `cryptography==50.0.1` was installed and pinned for that archive.
- Added persistent OS ownership locks for maintenance tools, including path and
  case aliases, and an external restore marker reserving companion invalidation.
- Verified the full Python suite: **305 passed, 1 skipped**, with one existing
  FastAPI/Starlette test-client deprecation warning. All **58 frontend tests**,
  the frontend production build, `cargo fmt --check`, and
  `cargo check --locked --offline` pass. No native bundle rebuild/install was run.
  The pre-existing date-dependent intraday timestamp fixture is now deterministic;
  production rolling-window behavior was not changed.

The original-browser export was supplied and validated on 2026-09-12:
`/Users/joe.rennick/Downloads/scanner-browser-export-2026-09-12T18-37-44-036Z.json`.
It identifies `http://127.0.0.1:5173`, confirms the browser write pause, and
contains 8 Planned Trades, 37 candidate edits, 48 valuation-assumption records,
and 4 settings groups. Schema/count/digest validation passed. Source database
counts remain unchanged, and a fresh source-holder check passed.

No custom data paths were found in the selected repository's data files, IDE
run configurations, saved scan output references, or the current scanner-related
environment. All saved runs reference `output/watchlist.csv`. The backup now
also captures the typed effective settings of its process; historical per-run
configuration remains in the saved scanner records.

The user completed the local hidden prompts and supplied successful output.
**The original-data backup/isolated-restore prerequisite in Section 7.2 passed.**
This is not completion of the later active-store activation/rollback work.

- Backup: `~/Library/Application Support/Swing Scanner/backups/phase1-2026-09-12`.
- Isolated restore: `/private/tmp/scanner-phase1-restore-2026-09-12`.
- Backup ID: `21177866cdb84b968fc65b590cf9fbad`.
- Verified at: `2026-09-12T19:08:41.737966+00:00`.
- Reconciled 13 scans / 2,230 rows, 1 watchlist / 7 items, all four browser
  collections, six backup files, and one decrypted credential. The user retrieved
  and re-entered their separately saved passphrase; it was never sent through chat.
- Independently checked the manifest and restore evidence, rehashed all six files,
  and reconciled original source business schemas/row digests after implementation.
  `active_store_imported` remains **false**.

Implemented after passing that prerequisite:

- `ApplicationPaths`: absolute platform defaults and explicit data/cache/report/log
  overrides, with cache/durable overlap rejection including case aliases. Default
  business and credential stores no longer share the market cache database.
  Explicit legacy `ScannerSettings(market_data_cache_path=...)` overrides retain
  old mixed-store compatibility unless business/credential paths are also supplied.
- Ownership leases shared by backend/sidecar lifespans, all nine application CLIs,
  queued/running jobs, six SQLite store types, and CSV journal instances. Stores
  acquire before creating/opening their database; context-managed connections close
  deterministically. Maintenance tools still use their stricter standalone guard.
- Runtime refuses unsupported SQLite versions (existing store schema remains 0;
  versioned migration is still to be implemented), external restore markers and
  a pending-import guard. Missing populated-store credential keys cannot be replaced.
- Report/log/journal/chart-cache defaults no longer depend on repository cwd.
  The Tauri host passes resolved paths to Python. SEC identity is explicitly
  configured through `SEC_USER_AGENT`; no personal default remains in `src`.
- Tests isolate all path defaults before importing application modules and cover
  independent roots, case aliases, cross-process exclusion, CLI contention,
  background ownership after shutdown, future-schema refusal and missing keys.

**Immediate next work:** implement versioned production browser-business
repositories and a previewed, idempotent staged import with crash-safe
activation/rollback. Preserve the backup, original source and browser records.
Before activation, reconcile against this capture again or recapture if edited.
The actual selected root contains `migration-pending.json` with this backup ID;
normal startup intentionally stops so it cannot present an empty new store.
Do not manually remove it. The staged activation must retire it only after
reconciliation succeeds. The isolated verification directory is not an active
runtime root and does not contain a plaintext restored credential store.

Then finish `/api/v1` and path/file/runtime adapters, setup configuration, cache
eviction and import interruption acceptance, and the installed/no-repository proof.
No production data was imported, no native bundle was rebuilt or installed,
and Phase 1 remains incomplete. Do not start later phases.

The frontend is listening on `http://127.0.0.1:5173`; availability must be checked
on resume. Do not automatically start the legacy backend during the write pause.
The supplied export establishes the original origin as `http://127.0.0.1:5173`.
Keep editing paused while continuing the import; if edits resume, a fresh capture
is required before import. Do not start the backend to bypass the pending guard. Recovery
passphrases are entered only at local hidden CLI prompts and retained separately
in the user's password manager, never in chat or beside the backup.

The user accepted the first architecture audit's improvements on 2026-09-06,
then requested a second independent audit and approved all six plan corrections
on 2026-09-07. A third audit found three additional refinements, also approved
for the plan on 2026-09-07. Only the Apple plan and this handoff changed in these
documentation updates; Phase 1 and later work were then unimplemented. Section 18
maps all three audits to requirements, phases, and acceptance checks.
User-selected compatibility targets remain macOS Tahoe 26+ and iPhone 15+.
The minimum iOS version awaits user confirmation; iOS 26.0 was an assistant's
provisional proposal, not an approved requirement. Resolve it before finalizing
the Phase 5 deployment target; it does not block Mac work. Apple Silicon remains
the first Mac architecture; Intel support is an optional expansion.

The second-audit corrections require:

- Phase 1 exclusive data-root ownership across backend and maintenance entry
  points, before opening destination databases, held through import/restore.
- Backup restoration to invalidate phone authorization and require re-pairing;
  establish the restore boundary in Phase 1 and test companion invalidation in
  Phase 5, including restore of a backup taken before revocation.
- Temporary connection loss to preserve pairing and unexpired read-only cache,
  separately from explicit unpairing and server revocation.
- Separate local bundle-integrity, Apple-issued hardened-runtime, and actual
  distribution-signing evidence. No ad-hoc test implies production acceptance.
- iPhone provisioning/team/device setup before the Phase 5 proof, plus renewal
  and in-place upgrade/reinstall acceptance in Phase 6.
- A confirmed minimum iOS and actual available device/OS matrix, with coverage
  gaps recorded rather than claimed as passes or hidden by simulator results.

The third-audit refinements add:

- A Phase 2 gap-free socket handoff: inherit the still-bound loopback socket,
  confirm the owned child is listening, then verify readiness and publish the
  endpoint. The current Phase 0 free-port probe does not satisfy this new gate.
- A watchlist command-ID/revision/retry contract defined in Phase 2 and enforced
  across all writers before Phase 5 mobile editing. Retrying an old accepted add
  must not undo a subsequent removal; no new offline-editing scope is added.
- A narrow Phase 1 exception permitting explicitly selected repository data to
  be read for migration. Preserve source records/schemas/keys and keep normal
  runtime independent of the repository after import.

The built proof is at:

```text
ui/src-tauri/target/release/bundle/macos/Swing Scanner.app
```

Read `docs/PHASE_0_VERIFICATION.md` for the completed acceptance evidence and
runtime-isolation procedure.

Before changing anything:

1. Work in `/Users/joe.rennick/scanner`.
2. Read this file completely.
3. Read `APPLE_APPLICATION_IMPLEMENTATION_PLAN.md`, especially **Current
   implementation status**, Sections 2.1, 6, 7, and 18, and **Phase 1**.
4. Inspect `git status` and preserve the completed Phase 0 work and any remaining
   local changes.
5. Do not start PostgreSQL/MariaDB, the iPhone app, public distribution, or the AI
   Analysis implementation. Their order is documented in the Apple plan.

Suggested opening prompt:

> Work in `/Users/joe.rennick/scanner`. Read `SESSION_HANDOFF.md` and
> `APPLE_APPLICATION_IMPLEMENTATION_PLAN.md` completely, inspect any remaining
> local changes, and continue with Phase 1. Preserve the completed Phase 0
> work. Inventory filesystem and browser-held business data, including Planned
> Trades, and complete the coordinated backup/restore gate in Section 7.2 before
> changing application paths or performing an import. Apply Section 7.3's
> exclusive data-root ownership before opening any active destination database.

## Current product direction

Swing Scanner is being converted from a browser-run React/FastAPI application
into a self-contained Mac application, followed later by a trimmed-down iPhone
companion.

The approved order is:

1. Finish the local Mac packaging proof of concept (Phase 0; complete).
2. Centralize paths, export/import browser business records, and migrate local
   data only after a coordinated backup and successful restore, with exclusive
   ownership established before destination database access (Phase 1).
3. Add secure desktop integration, host-owned Keychain access, durable local
   jobs, versioned API adapters, and the packaged scan/PDF/reopen and local
   bundle-integrity checks (Phase 2). Record Apple-issued hardened-runtime
   evidence separately, or explicitly defer that profile to Phase 4. Implement
   the socket handoff and define the ordinary watchlist mutation/retry contract.
4. Implement the separately approved AI Analysis plan on those foundations
   (Phase 2A).
5. Package and verify all existing application features (Phase 3).
6. Create the local Mac release (Phase 4).
7. Prove discovery, certificate trust, pairing, and revocation on a physical
   iPhone after confirming the OS target, device matrix, and local provisioning.
   Include restore-safe revocation and distinct temporary-loss/unpairing states
   before building mobile screens. Enforce the shared watchlist retry/conflict
   contract before enabling mobile editing, then complete the companion
   (Phases 5 and 6).
8. Consider a hosted backend and public distribution only after a separate
   approval (Phase 7). PostgreSQL is the default recommendation; MariaDB may be
   selected for a demonstrated operational/workload advantage. Synchronization
   requires its own authority, conflict, deletion, and retry design.

PostgreSQL is deliberately deferred. It is not needed for the local Mac app or
the first same-network iPhone companion. SQLite remains the local source of
truth for the local Mac and LAN companion. A future hosted engine is a separate
choice; neither PostgreSQL nor MariaDB is a local-installation prerequisite.

## Completed Phase 0 implementation

- Installed the Apple Silicon stable Rust toolchain:
  - `rustc 1.98.1`
  - `cargo 1.98.1`
- Added Tauri 2 dependencies and desktop scripts to `ui/package.json`.
- Added the Tauri host under `ui/src-tauri/`.
- Added a PyInstaller one-directory sidecar build:
  - `packaging/desktop_sidecar.spec`
  - `packaging/build_desktop_sidecar.sh`
  - `packaging/requirements.txt` pins `pyinstaller==6.22.2`
- Added the minimal desktop FastAPI sidecar in
  `src/scanner/desktop/sidecar.py`.
- The sidecar:
  - binds to `127.0.0.1` on a dynamically selected port;
  - requires a per-launch bearer token;
  - exposes authenticated health and shutdown endpoints;
  - smoke-imports NumPy, pandas, matplotlib, lxml, Pillow, certifi, and Uvicorn.
- The Rust/Tauri host:
  - selects a free loopback port;
  - generates a random in-memory bearer secret;
  - starts and owns the packaged backend process;
  - provides runtime configuration to the WebView;
  - requests graceful shutdown and uses a bounded forced-shutdown fallback.
- Added `ui/src/desktop/DesktopProofOfConcept.tsx` with startup, connected,
  dependency-version, failure, and retry states.
- Browser mode still renders the existing full application. Tauri mode renders
  only the Phase 0 readiness screen by design.
- Added bearer-token support to the shared API client and corresponding React
  coverage.
- Added three Python tests for authentication, dependency reporting, and
  graceful shutdown.
- Built an Apple Silicon PyInstaller sidecar and copied it into the Tauri
  resources directory. Generated build and resource output is ignored by Git.
- Updated `APPLE_APPLICATION_IMPLEMENTATION_PLAN.md` so it reflects the actual
  Phase 0 scope, status, exit criteria, and delivery order.
- Installed Rust formatting support and passed `cargo fmt --check`.
- Downloaded and compiled the Tauri dependencies; retained the generated
  `ui/src-tauri/Cargo.lock` for repeatable dependency resolution.
- Fixed the first compile's missing-icon failure by adding SVG, PNG, and ICNS
  icon assets and explicit Tauri icon configuration.
- Produced the 132 MB Apple Silicon `Swing Scanner.app` and opened it through
  Finder. Its native WebView rendered “Packaged backend connected” and all
  seven dependency versions, verified through macOS accessibility.
- Confirmed one host owns one backend child, dynamic loopback binding, HTTP 401
  on unauthenticated health, and no remaining processes after normal quit.
- Copied the app outside the repository, occupied ports 5173 and 8000, and
  launched it under a sandbox denying the repository, virtual environments,
  and external Python installations. The isolated WebView still connected,
  and normal quit left no backend child.
- Verified authentication, CORS, dependency imports, and graceful shutdown
  separately against the isolated packaged sidecar.
- Recorded the evidence in `docs/PHASE_0_VERIFICATION.md`. Screenshot capture
  was blocked by macOS; rendered content was checked with the authorized
  accessibility interface. No screenshot-based layout review is claimed.

## Exact next steps

1. Read `docs/PHASE_1_DATA_MIGRATION.md` and the Phase 1 requirements. The Phase 0
   evidence remains historical and does not need repeating for inventory work.
2. Inventory SQLite databases, credential stores and encryption-key files,
   reports, exports, caches, configuration, repository-relative paths, and browser
   storage. Planned Trades currently live in browser `localStorage` and need an
   explicit original-origin export; copying databases cannot migrate them.
3. Follow Section 7.2: coordinate a write pause, use SQLite snapshots, protect
   credential recovery material, reconcile manifests, and restore into an
   isolated data root. Complete that gate before changing paths or importing
   into an active destination. Keep source business records intact. Require the
   Section 7.3 ownership protocol before opening destination databases, and hold
   ownership through staged activation/recovery. Reserve restoration state
   outside the payload for later companion-authorization invalidation. Explicitly
   selected repository sources are permitted as read-only migration inputs under
   Section 7; do not initialize source schemas or create missing source keys.
4. Implement centralized platform-resolved paths, development/test overrides,
   staged/idempotent import, business-record repositories, and the initial API
   and runtime adapter boundaries. Store disposable caches in `Library/Caches`.
   Keep existing browser consumers working during migration.
5. Verify every Phase 1 exit criterion, including competing app/CLI/maintenance
   processes and interrupted activation, before marking that phase complete.
6. Do not commit or push until the user asks. Do not include `.idea/` or
   generated build/resource output in a commit.

Phase 0 does not need repeating before the Phase 1 inventory. Rebuild and rerun
packaging checks when runtime or packaging changes require them. The repeatable
build command is `npm run desktop:build` from `ui`.

## Verification baseline

Current Phase 1 preparation checks on 2026-09-11:

- Migration and focused existing Python coverage: 42 passed, one dependency
  deprecation warning. Command: `PYTHONPATH=src .venv313/bin/pytest
  tests/test_migration.py tests/test_desktop_sidecar.py tests/test_secret_store.py
  tests/test_saved_watchlists.py tests/test_scanner_results_store.py -q`.
- React: 58 passed across 12 test files; production frontend build passed.
- CLI help and read-only production inventory ran successfully. The local Vite
  server served `/migration`; actual original-browser storage has not been read.
- Source preservation tests compare logical SQLite rows/schema and durable file
  digests, permitting documented WAL/SHM snapshot bookkeeping. No production
  credential decryption or provider requests were performed.
- No native rebuild or full Python suite rerun; retain the historical exception
  below. Phase 0's native proof still has its original scope and limitations.

The most recent recorded checks are:

- Desktop sidecar tests: 3 passed.
- React tests: 52 passed.
- React production build: passed.
- Rust formatting and `git diff --check`: passed.
- Complete Tauri application build: passed after adding the required icons.
- All Phase 0 native runtime acceptance criteria: passed.
- Full correctly configured Python suite, recorded baseline from the prior
  session (not rerun in this continuation): 239 passed, 1 skipped, 1 failed.

The single Python failure is an existing date-sensitive test:

```text
test_market_data_history_endpoint_returns_intraday_timestamps
```

Its fixed `2026-08-28` fixture is removed by a relative one-day trim when run
after that date. It predates Phase 0 and should remain reported separately from
packaging regressions unless explicitly fixed.

The application is a local development proof. Strict deep code-signature
verification does not pass for the unsigned bundle. Phase 2 now requires an
earlier local signing/layout and strict bundle-integrity check before Phase 2A.
Section 6.1 separates that mandatory development profile from an early
Apple-issued hardened-runtime test when a suitable identity is available.
Unverified hardening must remain explicitly deferred to Phase 4, where the
actual Developer ID, reviewed production entitlements, notarization, and
Gatekeeper checks must pass before distribution. Do not treat this proof as a
release artifact for other Macs. No application tests were rerun for the
2026-09-07 documentation-only updates; the baseline above is unchanged.

For the subsequent user-requested commit on 2026-09-07, the focused sidecar tests
were rerun (3 passed, one dependency deprecation warning), along with React tests
(52 passed), the React production build, Rust formatting, and whitespace checks
(all passed). The full Python suite and native packaging/runtime acceptance were
not rerun; their recorded results and limitations above still apply.

Useful verification commands:

```bash
cd /Users/joe.rennick/scanner
PYTHONPATH=src .venv313/bin/pytest tests/test_desktop_sidecar.py -q

cd /Users/joe.rennick/scanner/ui
npm test
npm run build
```

## Pre-commit working-tree snapshot

This inventory records the state before the user-requested publication. It is
historical, not a claim that the listed project files remain uncommitted.

Tracked files modified by Phase 0:

```text
.gitignore
APPLE_APPLICATION_IMPLEMENTATION_PLAN.md
ui/package-lock.json
ui/package.json
ui/src/api/client.test.ts
ui/src/api/client.ts
ui/src/main.tsx
ui/src/styles.css
```

Untracked Phase 0 source/configuration files:

```text
packaging/requirements.txt
packaging/build_desktop_sidecar.sh
packaging/desktop_sidecar.spec
src/scanner/desktop/__init__.py
src/scanner/desktop/sidecar.py
tests/test_desktop_sidecar.py
ui/src-tauri/Cargo.toml
ui/src-tauri/Cargo.lock
ui/src-tauri/build.rs
ui/src-tauri/capabilities/default.json
ui/src-tauri/icons/icon.svg
ui/src-tauri/icons/icon.png
ui/src-tauri/icons/icon.icns
ui/src-tauri/src/lib.rs
ui/src-tauri/src/main.rs
ui/src-tauri/tauri.conf.json
ui/src/desktop/DesktopProofOfConcept.tsx
docs/PHASE_0_VERIFICATION.md
```

Also untracked:

```text
SESSION_HANDOFF.md
.idea/
```

`SESSION_HANDOFF.md` is included in the requested project commit.
`.idea/` is local IDE metadata and must remain out of the application commit.

Generated content under `packaging/build/`, `ui/src-tauri/resources/`, and
`ui/src-tauri/target/` is intentionally ignored.

## Important implementation boundaries

- Phase 0 is deliberately isolated from production scanner data. Do not connect
  the full app or migrate mutable data merely to finish the proof of concept.
- Do not weaken loopback binding or bearer authentication to make the build
  easier.
- Do not hard-code ports 5173 or 8000 for the packaged backend.
- Phase 2 must replace the Phase 0 free-port probe with continuous socket
  ownership through handoff; publish connection details only after owned-child
  acknowledgement and authenticated readiness.
- Do not persist the per-launch bearer token.
- Do not require a system Python installation or `.venv313` at runtime.
- Preserve the existing browser development workflow.
- Mutable data must eventually move to standard macOS application directories,
  but that work belongs to Phase 1 and requires a validated backup/restore first.
- Explicit read-only migration may use user-selected legacy repository data.
  That exception does not permit runtime writes, source schema initialization,
  missing-key creation, or continued runtime dependence on the source.
- Exclusive data-root ownership is a Phase 1 safeguard, not a Phase 2 UI feature.
  Keep the lock outside replaced directories and ensure every application entry
  point accessing that root respects it; stop uncooperative legacy writers.
- Browser business records must move through an explicit export/import into
  SQLite; only ordinary versioned display preferences remain in `localStorage`.
- Preserved legacy credential sources and encrypted recovery archives are
  distinct from the active desktop store's no-SQLite-secrets requirement.
- Massive users will provide their own API key or supported authorization. The
  application must never collect a Massive username or password.
- `AI_ANALYSIS_IMPLEMENTATION_PLAN.md` is approved product work, but its
  implementation waits until all revised Phase 1 and Phase 2 gates pass,
  including the packaged production workflow and durable local job lifecycle.

## Main reference documents

- `docs/PHASE_1_DATA_MIGRATION.md` — current Phase 1 inventory, tested recovery
  tooling, original-data backup instructions, and remaining runtime work.
- `APPLE_APPLICATION_IMPLEMENTATION_PLAN.md` — source of truth for Mac/iPhone
  architecture, phase order, PostgreSQL timing, testing, and release gates.
- `docs/PHASE_0_VERIFICATION.md` — completed native packaging acceptance
  evidence, isolation procedure, and known verification limits.
- `AI_ANALYSIS_IMPLEMENTATION_PLAN.md` — source of truth for the future AI
  watchlist-analysis workflow, follow-up refinement, history, and AI-created
  watchlists.
- `README.md` — existing browser development and project information.
