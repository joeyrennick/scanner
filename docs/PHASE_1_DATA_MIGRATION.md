# Phase 1 data inventory and recovery preparation

## Latest checkpoint — SEC application contact setup

On 2026-09-13 the versioned application configuration and **SEC Contact Setup**
form were implemented and tested. See `PHASE_1_APPLICATION_SETUP.md`. The contact
is not a password or login. It is explicitly supplied by the user, saved separately
from credentials at `configuration/application-settings.json`, and used in future
SEC request headers. The archived `configuration/scanner-settings.json` is not
applied live. Existing backups/source data are not rewritten. The user still needs
to choose and save their contact email; live setup is revision 0/source `missing`.

**402 Python tests passed / 1 skipped**, one existing dependency warning;
**122 frontend tests and build passed**. Tests use isolated roots and mocked SEC
requests, including real TS/Python setup transport across process restart.
After the user confirmed jobs were stopped, the backend was cleanly restarted
(PID 74108, port 8000; Vite 87647 on 5173). Live record envelope hashes remain
unchanged: 8 / 37 / 48 / 4. Setup GET returns 200/no-store. No real setup writes,
provider calls or credential reads were made. Browser use can resume; refresh
Settings to complete contact setup. Do not repeat backup/import/password steps.
Remaining path independence and packaged/no-repository/relaunch acceptance stay
open; the native app is still the Phase 0 proof. Older checkpoints follow.

## Previous checkpoint — runtime/file adapters and confirmed browser switch

On 2026-09-13 the user confirmed completing the database-backed browser switch.
No repeat import, backup or recovery password is required. They confirmed there
were no running jobs before the next development-backend restart.

The runtime/API/file adapters now isolate connection details and file presentation
from the pages. All existing API hooks and the business provider use the injected
connection. Versioned report/job-output downloads take IDs, not client paths;
file descriptors are opened relative to approved roots without following
symlinks. Key/database/nonregular files, traversal and unmanaged outputs are
rejected. Existing report IDs and legacy endpoints remain compatible; HTML may
be downloaded but not previewed inline. Auth tokens stay in headers, never URLs.
Browser exports, drafts and CSVs share the file presenter and retain original
business data. The native proof exposes no native-file or full-scanner capability.

`/api/v1/runtime` reports API compatibility, implemented capabilities and resolved
paths without creating stores or returning credentials. Settings now shows this
information. Python: **368 passed / 1 skipped**, one existing warning. Frontend:
**110 passed**, plus production build; the real API test bridge also verifies
runtime/PDF transport. No native bundle was rebuilt or installed.

The backend is running on port 8000 (PID 53818 at handoff) behind Vite on 5173.
All four live record checksums were unchanged across restart (8 / 37 / 48 / 4),
and the saved 36,633-byte PDF matched its disk file exactly through the new route.
Verification used GETs only and no provider calls or credential reads. Original
data and backups were not changed. Configuration/SEC identity setup, remaining
path independence and packaged/no-repository acceptance are the next Phase 1 work;
Keychain/full native integration remain later. Earlier checkpoints follow.

Latest checkpoint on 2026-09-13: staged first-import/activation, the production
browser-record repository/API and database-backed browser business UI are
implemented and tested (350 Python tests pass, 1 skip; 87 frontend tests and
build pass). See the latest checkpoint
in `SESSION_HANDOFF.md` for supported scope and interruption evidence. The
replacement backup `2d2cf0e78c1a4434b537d758d4f947cc` passed isolated restore at
`2026-09-12T23:47:45.520088+00:00` with the new saved recovery password. Six files,
all saved/browser records and one credential reconcile. Original source data and
both backups remain intact. `select-verified-backup` has safely reassociated the
pending gate with the new backup, preserving its predecessor. The real import
then completed at `2026-09-14T01:25:46.881544+00:00` (September 13 PDT), ID
`22085cefcf09428e9e68186e9fcfeb6e`. Active receipt, exact saved/browser records,
CSV/PDF hashes and the imported credential were independently verified. The
pending gate and activation journal are gone; original data and both backups
remain intact. No more password entry or repeat import is needed now.

Journal, Candidates, Fundamentals, and Settings now load/save the imported
collections. Loading is gated; writes are serialized with revision/tombstone
checks. Conflict/ambiguous failures freeze editing and retain a downloadable
in-memory draft until explicit discard/reload. No automatic retries or legacy
business localStorage fallback occur. Chart/navigation preferences use new
versioned keys; the original business keys are never rewritten or deleted.
Real TypeScript-to-Python/SQLite restart tests and rendered-page tests pass.
The frontend integration test requires the local `.venv313/bin/python` environment
(or `SCANNER_TEST_PYTHON` override), using temporary roots and no provider calls.

The local API was started on port 8000, behind Vite on port 5173; it holds the
active root's ownership lock. Live API GETs reconcile all four browser
collections exactly to the export (8 / 37 / 48 / 4). Browser editing was NOT
automatically resumed. In the original browser, visit `/migration`, close other
Scanner tabs, confirm, choose **Check imported database records**, and then
**Resume with imported database** after success. The first switch compares the
exact original records and origin to the completed import. Subsequent switches
recognize legitimate database edits without replacing them from the old browser
copy; that copy's digest must remain unchanged. The export is archival only after
the switch and must not be described as a backup of later database edits.

Original-browser confirmation, remaining adapters/configuration, nonempty-store
replacement and packaged acceptance are unfinished. No native rebuild/install
was done; the Mac app still shows the Phase 0 proof screen. Earlier preparation
details below are historical where superseded by this checkpoint.

Started 2026-09-11; updated 2026-09-12. Phase 1 is **in progress**. The real
coordinated backup/isolated-restore prerequisite **passed**. Runtime path and
ownership foundations are implemented, but no active-store import has run.
Original databases, keys and browser records remain intact. The previously built
Phase 0 application has not been rebuilt or installed with these source changes.

## Observed filesystem inventory

Read-only inspection of `/Users/joe.rennick/scanner/output` on 2026-09-11:

| Source | Classification | Observed records/size |
| --- | --- | --- |
| `market_data_cache.sqlite` | Mixed business, cache, and credential database; owner UID 501; SQLite user_version 0 | 201,478,144 bytes |
| `scanner_runs` / `scanner_results` tables | Durable saved scans, including edited levels and original settings snapshots | 13 runs / 2,230 rows |
| `saved_watchlists` / `saved_watchlist_items` tables | Durable user watchlists | 1 list / 7 items |
| `secrets` table / matching `market_data_cache.key` | Legacy encrypted credentials and recovery key | 1 credential / 44-byte encoded key; key mode 0600 |
| `price_bars` / `cache_fetches` tables | Rebuildable market cache | 898,936 / 10,483 rows |
| `fundamental_analysis_cache` / `sec_fundamentals_cache` | Rebuildable provider/analysis cache | 415 / 4,722 rows |
| `sqlite_sequence` | Preserve business autoincrement state | 2 rows |
| `watchlist.csv` | Durable latest scan export; also referenced by historical scan metadata | 221,617 bytes |
| `watchlist_reports/*.pdf` | Durable saved report | 1 PDF, 36,633 bytes |
| `logs/*.log` | Disposable operational logs; excluded from essential backup | 17 files |
| `scanner_runs.sqlite3` | Empty artifact; not the actual scan store | 0 bytes; preserved at source, not initialized |

No `trade_journal.csv` currently exists in the inspected output directory. The
legacy CLI supports it and the backup allowlist includes it if present. Reports
are currently discovered by directory traversal; there is no separate report
index table. Historical `scanner_runs.output_file` values describe exports and
can refer to a repeatedly overwritten CSV; do not claim the CSV recreates every
historical scan. The saved result rows remain authoritative for those scans.

The inspection did not open legacy store classes, migrate schemas, create missing
keys, decrypt production credentials, or call a provider. At inspection time,
`lsof` found no open source files and neither development port had a listener.
This is a point-in-time observation, not a standing write pause.

## Browser storage inventory

The user supplied the original-browser export on 2026-09-12 at
`/Users/joe.rennick/Downloads/scanner-browser-export-2026-09-12T18-37-44-036Z.json`.
Its schema, SHA-256 payload digest and counts validate: **8 Planned Trades,
37 candidate edits, 48 valuation-assumption records, 4 settings groups**.
It was captured at `2026-09-12T18:37:44.031Z` from
`http://127.0.0.1:5173`, export ID `91b86a6b-02ba-4674-82e8-fa46b39f6df9`,
with `writePauseConfirmed: true`. `localhost` and `127.0.0.1` are different storage
origins. No browser profile files were scraped.

| Keys | Classification and treatment |
| --- | --- |
| `planned-trades` | Durable business records; preserve original IDs and every trade field |
| `swing-scanner.candidates.chart-state` | Mixed: preserve entry/stop/target per ticker; chart dimensions, zoom and pan are display preferences |
| `swing-scanner.fundamentals.v1` | Mixed: preserve `assumptionsByTicker`; ticker, filters, selected tab, scroll and job display state are UI/rebuildable state |
| `swing-scanner.recommendation-settings` | User defaults; export only known typed configuration fields |
| `swing-scanner.market-data-settings.v2`, `.cache-settings`, `.appearance-settings`, `.display-settings` | Export known typed configuration fields; never credential fields |
| `swing-scanner.daily-scanner.*` | Strategy selection, filters, columns, selected ticker: UI preferences |
| Remaining `swing-scanner.candidates.*` | Selection, sort, filters, columns, chart frequency, panel width: UI preferences |
| `swing-scanner.journal.selected-*` | UI selection; not additional trades |
| `swing-scanner.saved-watchlists.page.v1`, `swing-scanner.recent-ticker.v1` | UI navigation/selection state; watchlists themselves live in SQLite |
| `swing-scanner.migration.pause.v1` | New operational write-pause marker; not user data or a credential |
| Unknown/unrelated keys | Never included in ordinary export; review newly discovered scanner-owned data before declaring inventory complete |

Some existing display keys lack explicit versions. Versioning and API migration
remain later Phase 1 work. The export leaves **all** original keys intact.

A fresh export supplied while checking the pause on 2026-09-12 also validates:
`/Users/joe.rennick/Downloads/scanner-browser-export-2026-09-12T23-41-41-262Z.json`,
captured at `23:41:41.259Z`, ID `b83655b0-1fbc-44a4-ad0e-975b5a8a43ef`.
It confirms the same origin/write pause and contains exactly the same business
records as the earlier export. The waiting replacement-backup runner therefore
remains valid with its earlier input; it was not edited while running. Keep both
exports, and keep editing paused through backup, verification and import.

Backend settings currently come from tracked Python defaults, explicit CLI/API
arguments, and environment overrides. Inventory the stopped backend's effective
nonsecret overrides and any custom journal/report/configuration paths before the
actual backup gate. A backup of `output` alone cannot certify undiscovered custom
paths. Retain the source revision and protected configuration records; provider
environment secrets need separate recovery, never an ordinary configuration dump.

The 2026-09-12 follow-up found no additional data/configuration files in the
repository, no IDE run configurations, and no scanner-related overrides in the
current tool environment. Every saved scan references `output/watchlist.csv`.
Source database, key and CSV modification times and business counts are unchanged.
This supports using the selected output root and tracked defaults for this
capture; it is not a claim about unselected files elsewhere on the Mac. The
backup includes `configuration/scanner-settings.json` with the typed effective
settings of the backup process, including any nonsecret overrides in its Terminal
environment. Historical per-run settings are retained in the database snapshot.

## Implemented preparation

- `/migration` is a standalone browser export page, also linked from Settings.
  It avoids mounting the normal app and its storage normalization effects.
- A user-confirmed browser pause persists across reloads and updated tabs.
  Updated clients reject new API requests during the pause, including GETs
  because legacy GET handlers can initialize databases or fetch/cache data.
  Close older tabs and stop the backend separately: an old already-loaded client
  or an in-flight request cannot be stopped by this browser marker alone.
- Export v1 contains the exact payload JSON, SHA-256 digest, original origin,
  export ID/time, stable record IDs, and per-collection counts. Known fields,
  types, finite numbers, duplicate IDs, version, and size are validated. It
  rejects changes detected while hashing and never silently erases malformed data.
- `python -m scanner.migration inventory` reports file metadata, database schema
  versions, column names and counts without returning secrets or business rows.
- `backup` acquires source/destination ownership, requires a stopped-source
  acknowledgement and no open source files, uses SQLite's backup API, then
  reconciles business records/schema digests and source files before finalizing.
  Unknown files/tables, missing keys, and incompatible schema versions stop it.
- Business snapshots exclude rebuildable tables and the secrets table. VACUUM
  removes their discarded pages from the snapshot. Source records remain intact.
- Credential recovery uses a separate SQLite projection retaining the complete
  original secrets table/schema and matching original key, encrypted together.
  It is a recoverable credential database, not a byte copy of the mixed cache DB.
  Encryption uses Fernet and Argon2id (64 MiB, three iterations, four lanes), with
  a fresh salt and a separately retained user passphrase. `cryptography==50.0.1`
  is pinned. Provider connectivity is never required for recovery validation.
- `verify` restores into a **new** isolated root, checks every file, database
  integrity, foreign keys, business record/schema digests and browser records,
  and verifies legacy credential decryption in memory. Browser records are
  restored into SQLite under their origin/collection/ID for reconciliation.
  This recovery table is not yet the production business repository/API.
- Ownership uses OS `flock`, a persistent lock file outside the replaceable root,
  resolved symlinks and conservative case/Unicode normalization. This prevents
  the `output`/`OUTPUT` alias bypass on case-insensitive macOS volumes. Case-only
  sibling roots on case-sensitive volumes are conservatively serialized too.
- A durable marker outside each restore payload keeps companion access disabled
  and pairing reset required. Failed restores retain a pending marker and partial
  isolated output for diagnosis. No existing root is replaced, and there is no
  active-store activation command yet.

Shared ownership now also protects backend/sidecar lifespans, all nine application
CLIs, queued/running background jobs, six SQLite store types, and CSV journal
instances. It is retained while connections or jobs remain live, including after
server shutdown. Store constructors acquire before creating database parents or
opening SQLite. Existing nonzero schema versions are rejected before schema changes;
versioned production migrations are still pending. The tools still require older
legacy writers and external database tools to be stopped: they do not honor these
new locks. **Packaged runtime acceptance remains required before Phase 1 can pass.**
The restore marker establishes a boundary for later work; companion listener
enforcement and restoration onto active stores are not implemented.

Implementation references: [SQLite backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup)
and [authenticated credential archive encryption](https://cryptography.io/en/latest/fernet/).

## Original-data backup and restore procedure

1. Review the inventory above, identify custom data/configuration paths, and
   finish/drain existing jobs. Retain the effective configuration and source
   revision. The original-origin browser export is required even if it reports
   zero Planned Trades.
2. In the original browser, open `/migration` at the exact scanner address.
   Close other scanner tabs/windows, confirm the page's checklist, and choose
   **Pause editing and export records**. Save the JSON outside the source output
   directory and verify the displayed counts. Keep editing paused through the
   coordinated capture. If records are edited afterward, export and capture again.
3. Stop the legacy backend and any scanner CLI/database tools. Save a recovery
   passphrase of at least 16 characters in a password manager. Enter it only at
   the local hidden terminal prompts; do not paste it into chat, shell arguments,
   environment variables, the repository, or a file beside the backup.
4. From the repository, run the following with real selected paths. The backup
   directory must be new and outside the source tree. Parent directories may be
   created automatically. The tool refuses to overwrite an earlier attempt.

```bash
PYTHONPATH=src .venv313/bin/python -m scanner.migration inventory \
  --source-root /Users/joe.rennick/scanner/output

PYTHONPATH=src .venv313/bin/python -m scanner.migration backup \
  --source-root /Users/joe.rennick/scanner/output \
  --browser-export /absolute/path/to/scanner-browser-export.json \
  --destination '/Users/joe.rennick/Library/Application Support/Swing Scanner/backups/phase1-2026-09-11' \
  --source-writers-stopped

PYTHONPATH=src .venv313/bin/python -m scanner.migration verify \
  --backup '/Users/joe.rennick/Library/Application Support/Swing Scanner/backups/phase1-2026-09-11' \
  --restore-root /private/tmp/scanner-phase1-restore-2026-09-11
```

5. Retrieve the passphrase from the password manager for the separate verify
   invocation. Successful decryption here demonstrates that recovery material is
   available separately from the archive. Review `verification.json` in the
   isolated root: counts/digests, report files, browser records and credential
   count must reconcile. Retain the backup and recovery instructions.

   As of 2026-09-12, `backup --verify-root /absolute/new/restore/root` also runs
   verification immediately after capture, with a separate hidden prompt for
   the saved passphrase. A prepared runner using the actual supplied export was
   opened in Terminal at
   `/private/tmp/scanner-phase1-recovery.0EspyE/Run Scanner Backup.command`.
   It uses backup directory `phase1-2026-09-12` and restore directory
   `/private/tmp/scanner-phase1-restore-2026-09-12`. The user completed all three
   hidden prompts successfully; the evidence is recorded below.
6. Record actual evidence and resolve custom configuration/path gaps before
   marking Section 7.2 complete. Fixture tests do not satisfy the original-data
   gate. Resume browser edits only after capture/verification; an eventual import
   will need a fresh coordinated capture if source records change meanwhile.

If capture fails, the absence of `manifest.json` marks it incomplete. If restore
fails, its marker remains `restoring`. Keep source/backup data intact, investigate
the error, and retry into another new directory. Never point the application at
an unverified root. Existing-root activation, rollback and interrupted-activation
recovery must be built and tested before migrating the real running application.

## Completed original-data recovery evidence

The user completed capture and independently re-entered the saved recovery
passphrase for verification on 2026-09-12. No passphrase was exposed to chat.

- Backup root: `/Users/joe.rennick/Library/Application Support/Swing Scanner/backups/phase1-2026-09-12`.
- Restore root: `/private/tmp/scanner-phase1-restore-2026-09-12`.
- Backup ID: `21177866cdb84b968fc65b590cf9fbad`.
- Verification time: `2026-09-12T19:08:41.737966+00:00`.
- Saved scans: 13 runs / 2,230 rows; watchlists: 1 list / 7 items.
- Browser collections: 8 Planned Trades, 37 candidate edits, 48 valuation-assumption
  records, 4 settings groups. Counts and original records reconcile in the restore.
- Six backup files verified, including configuration/CSV/PDF; one credential
  decrypted successfully in memory. `active_store_imported: false`.

The manifest and restore evidence were independently checked on disk; all six
backup files were rehashed and original source business schema/row digests still
matched after runtime work. This passes the prerequisite recovery exercise, not
active-store activation or rollback acceptance. Keep the backup and separately
saved passphrase; the isolated `/private/tmp` restore is verification evidence,
not the permanent recovery copy or an active runtime root.

## Implemented runtime foundations

`scanner.config.paths.ApplicationPaths` resolves absolute paths without creating
files. Defaults on this Mac are:

| Purpose | Default location |
| --- | --- |
| Application root | `~/Library/Application Support/Swing Scanner` |
| Business SQLite | `<root>/data/scanner.sqlite` |
| Temporary Phase 1 legacy credential store | `<root>/credentials/legacy.sqlite` plus matching key; host-owned Keychain is Phase 2 |
| Reports and latest watchlist | `<root>/reports` and `<root>/reports/watchlist.csv` |
| CSV journal | `<root>/data/trade_journal.csv` |
| Backups | `<root>/backups` |
| Market/analysis cache | `~/Library/Caches/Swing Scanner/market/market.sqlite` |
| Chart caches / temporary exports | `~/Library/Caches/Swing Scanner/{matplotlib,fonts,exports}` |
| Logs | `~/Library/Logs/Swing Scanner` |

Use absolute `SCANNER_DATA_ROOT`, `SCANNER_CACHE_ROOT`, `SCANNER_REPORT_ROOT`, and
`SCANNER_LOG_ROOT` overrides together for isolated runs. Cache and durable roots
must not overlap, including aliases. The Tauri host passes these resolved locations
to Python. No normal runtime default in `src` contains `output/`.

For compatibility, explicitly overriding `ScannerSettings.market_data_cache_path`
still selects the legacy mixed database unless `business_data_path` and
`credential_data_path` are also supplied. This exception is not the new default
layout and must not be treated as a disposable-only cache during migration.

Runtime startup refuses an external restore marker or `<root>/migration-pending.json`.
The selected real root now has the latter with the verified backup ID, preventing
an empty active store from being initialized before staged import is implemented.
Do not bypass or manually remove it. Maintenance activation must retire it only
after successful reconciliation. No data/credential store has been created there.

Missing keys for populated legacy credential stores are recovery errors on reads
and writes; a new key is created exclusively, mode 0600, only for a new empty store.
Personal SEC defaults were removed; requests require an explicitly configured
`SEC_USER_AGENT`. Persistent setup UI/configuration remains to be completed.

## Remaining Phase 1 work

1. Add versioned production repositories/APIs for browser business data and a
   previewed, idempotent import preserving original IDs/values and source records.
2. Implement maintenance drain, staging, atomic activation/rollback and interrupted
   activation recovery under ownership before opening the active store. Reconcile
   the selected capture and retire the pending marker only after success.
3. Establish `/api/v1` conventions and path/file/runtime adapters without breaking
   browser consumers; keep only versioned UI preferences in browser storage.
4. Finish persistent setup configuration, including the user's SEC identity.
5. Verify deleting rebuildable caches leaves durable records/reports intact and
   validate complete default/explicit-override layouts after import.
6. Verify all Phase 1 exit criteria, including installed `/Applications` runtime
   with repository unavailable. Preserve Phase 0; do not start Phase 2A or mobile.

## Verification

The initial regression baseline was 15 focused Python tests and 52 frontend tests
passing. Final results for this work are recorded in `SESSION_HANDOFF.md`.
Tests cover source preservation, committed WAL data, missing/corrupt source/key,
unknown schemas/files, credential recovery, browser data validation, repeated
backup/restore refusal, tampering, wrong passphrases, path traversal, process and
alias contention, interrupted isolated restoration, runtime and CLI contention,
connection lifetime, queued/background ownership, unsupported database versions,
pending-import refusal and missing-key preservation. Current totals: 305 Python
tests passed, 1 skipped; 58 frontend tests passed. Frontend production build and
offline locked Rust check pass. Native packaging has not been rebuilt; these
changes do not connect Phase 0 to production data.
