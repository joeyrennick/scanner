# Apple Application Implementation Plan

- Finalized: 2026-09-04
- Last updated: 2026-09-07
- Repository: `/Users/joe.rennick/scanner`
- Status: Approved plan; Phase 0 complete; Phase 1 has not started
- Plan revision: First audit improvements accepted on 2026-09-06; six second-audit
  corrections and three third-audit refinements accepted on 2026-09-07.
  Requirements below are planned work, not completed implementation
- Delivery order: Local Mac desktop application first, trimmed-down iPhone
  companion second

## Current implementation status

Phase 0 completed on 2026-09-06 on the target Apple Silicon Mac. The native
application remains a packaging proof of concept; the full scanner workflow
will be connected in later phases.

Completed so far:

- Installed the stable Apple Silicon Rust toolchain.
- Added the Tauri 2 JavaScript API and CLI dependencies to the React project.
- Installed PyInstaller 6.22.2 in the Python 3.13 packaging environment and
  recorded it in `packaging/requirements.txt`.
- Added a minimal authenticated FastAPI desktop sidecar, PyInstaller
  one-directory specification, and repeatable sidecar build script.
- Produced an Apple Silicon one-directory sidecar containing the native Python
  dependency smoke checks.
- Added the Tauri host source, dynamic loopback-port selection, per-launch
  bearer secret, backend process ownership, readiness configuration, graceful
  shutdown request, and forced-shutdown fallback.
- Added a dedicated React Phase 0 startup, success, failure, dependency, and
  retry display while leaving browser mode on the existing full application.
- Added three passing Python sidecar tests.
- Increased the passing React test baseline from 51 to 52 tests with desktop
  bearer-header coverage.
- Confirmed that the production React build succeeds.

Final packaging and runtime verification:

- Installed `rustfmt`; `cargo fmt --check` passes.
- Downloaded and compiled the Rust/Tauri dependencies and generated `Cargo.lock`.
- Corrected the first build's missing-icon error by adding an SVG source and
  generated PNG/ICNS application icons.
- Produced the 132 MB Apple Silicon application at
  `ui/src-tauri/target/release/bundle/macos/Swing Scanner.app`.
- Opened it through Finder and verified the rendered “Packaged backend
  connected” screen and all seven dependency versions through macOS
  accessibility. macOS did not permit automated screenshot capture.
- Confirmed one native host owns one backend child bound to `127.0.0.1` on a
  dynamically selected port; unauthenticated health returns HTTP 401.
- Copied the complete application outside the repository and launched it with
  both ports 5173 and 8000 occupied, Python environment overrides removed, and
  sandbox rules denying access to the repository, virtual environments, and
  external Python installations. Its WebView still reached connected status.
- Verified missing/wrong-token rejection, CORS origin restrictions, dependency
  imports, and authenticated graceful shutdown against the isolated packaged
  sidecar.
- Normal application quit removed both host and backend in the Finder launch
  and isolated launch checks.
- Re-ran the relevant checks: 3 Python sidecar tests, 52 React tests, production
  frontend build, Rust formatting, and whitespace checks pass.

Evidence and reproduction details are in `docs/PHASE_0_VERIFICATION.md`.
The artifact is a local development proof; public-release signing and
notarization remain Phase 4 work. Phase 2 now includes an earlier packaging and
signing-feasibility check before AI implementation. Phase 0 proves startup and
dependency imports; it does not establish full-feature or distribution readiness.
Phase 1 starts with an inventory of filesystem and browser-held business data,
followed by a validated backup and restore exercise before path changes or import.

Current baseline exception:

- The correctly configured Python suite completed with 239 passing tests, one
  skipped test, and one existing date-sensitive failure in
  `test_market_data_history_endpoint_returns_intraday_timestamps`. Its fixed
  2026-08-28 fixture is removed by the relative one-day trim when the suite is
  run after that date. This failure predates the Phase 0 changes and must remain
  visible until corrected separately.

## 1. Product outcome

Convert Swing Scanner from a browser-based local development application into
a self-contained Mac desktop application. The Mac application will preserve the
full existing product and will start, monitor, and stop its own local Python
backend without requiring Terminal commands or a separately opened browser.

After the Mac application is stable, create a smaller iPhone companion from the
same React and API foundations. The iPhone application will focus on reviewing
results, charts, fundamentals, watchlists, reports, and AI findings instead of
reproducing every information-dense desktop control.

Initial builds will be installed locally and will not require submission to an
Apple store. Public distribution remains a later release phase.

## 2. Finalized architecture decisions

| Area | Decision |
| --- | --- |
| Delivery order | Build and stabilize the Mac application before beginning the iPhone application. |
| Application framework | Use Tauri 2 with the existing React, Vite, and TypeScript frontend. |
| Mac backend | Keep FastAPI and package the Python application as a managed Tauri sidecar. Do not rewrite the scanner in Swift or Rust. |
| Mac data model | Remain local-first and single-user. SQLite remains the canonical database. |
| Mac networking | Bind the packaged backend to loopback only and authenticate every application API request with a per-launch secret. |
| Credentials | Store Massive and OpenAI credentials in macOS Keychain. Never collect a Massive username or password. |
| Development fallback | Continue supporting environment variables and the existing browser development workflow. |
| Initial Mac architecture | Support Apple Silicon first. Intel/universal support is an optional product expansion, not a prerequisite for sharing with supported Apple Silicon Macs. |
| Initial distribution | Install development builds locally, then produce a directly downloadable signed and notarized application and DMG. The Mac App Store is not required. |
| iPhone role | Treat iPhone as a companion, not a complete copy of the desktop product. |
| iPhone backend | Initially connect to an explicitly enabled Mac companion service on the same trusted network. Do not attempt to run the Python scanner on iOS. |
| Shared code | Share domain types, API client code, state schemas, charts, summaries, and appropriate React components. Use platform-specific navigation and layouts. |
| API and platform boundaries | Establish versioned contracts and browser/desktop adapters in Phases 1 and 2; extend them for mobile in Phase 5. |
| Hosted database | Keep SQLite locally. PostgreSQL is the recommended default only if a hosted backend is separately approved; MariaDB remains an evidence-based alternative. |
| Public release | Defer App Store, multi-user cloud, subscriptions, and commercial distribution until their dedicated release gates are satisfied. |

### 2.1 Supported platform targets

| Platform | Minimum target | Acceptance requirement |
| --- | --- | --- |
| Mac | macOS Tahoe 26.0 or later, Apple Silicon | Test the packaged application on macOS 26.0 and the current supported 26.x release; Phase 0 evidence covers only macOS 26.5.2. |
| iPhone | iPhone 15 family or newer; minimum iOS version awaits user confirmation (26.0 is a provisional proposal only) | Record available physical iPhone 15/newer-model OS combinations and the minimum/current test matrix before Phase 5; network privacy and pairing require real-device evidence. |
| Intel Mac | Deferred, including Intel models able to run Tahoe | Add a separate Intel/universal target only after an explicit product decision and native-dependency verification. |

The user selected iPhone 15+ and macOS Tahoe 26+. Hardware generation and OS
version are separate requirements: the earlier iOS 26.0 baseline was an assistant
assumption, not a confirmed user decision. Confirm the minimum iOS version before
finalizing the iOS deployment target in Phase 5; this does not block Mac work.
New OS major releases require compatibility checks before being added to the
verified support matrix. Set deployment targets in build metadata and check
every packaged native dependency against the minimum OS; a build on macOS
26.5.2 alone does not establish compatibility with 26.0.

Build an executable compatibility matrix before the relevant acceptance work:

- Record each actual device model, architecture, installed OS/build, Xcode/SDK,
  available simulator runtime or Mac test environment, test owner, and evidence.
  Mark each required combination as available, to be obtained, or a coverage gap.
- Cover a physical iPhone 15 and a newer supported model using OS versions each
  can actually run. Do not require every hardware/OS cross-product, or assume a
  newer phone can run an OS older than its original supported version.
- Identify access to a device retained on the chosen minimum iOS version before
  promising physical minimum-version acceptance. Do not plan to downgrade the
  user's updated phone to create that test environment. Apple documents the
  [iOS downgrade limitation](https://support.apple.com/en-us/100100).
- Simulator API/UI checks supplement physical-device trust/privacy checks; they
  cannot turn an unavailable physical test into a pass. Record missing evidence
  explicitly and obtain a test device or an explicit user-approved support/test
  scope adjustment before claiming the affected acceptance complete. Do not
  silently raise the minimum OS or claim untested compatibility.

Record the approved matrix and results in the release manifest. These are
implementation targets, not claims that the unfinished application passes them.

## 3. Target runtime architecture

### 3.1 Mac desktop application

```text
Swing Scanner.app
├── Tauri host process
│   ├── native window and application menu
│   ├── backend lifecycle management
│   ├── application paths and file dialogs
│   └── update and platform integration boundary
├── compiled React/Vite frontend
│   ├── full desktop routes and controls
│   └── authenticated requests to the sidecar
├── packaged Python/FastAPI sidecar
│   ├── scan and fundamentals workers
│   ├── SEC and Massive integrations
│   ├── report generation
│   └── application API
└── immutable bundled assets
    └── fonts, templates, certificate roots, and native libraries

User Library directories (outside Swing Scanner.app)
├── Application Support/Swing Scanner/   databases, reports, backups
├── Caches/Swing Scanner/                rebuildable caches and temporary exports
└── Logs/Swing Scanner/                  rotating logs
```

The Tauri host is the parent process. At launch it will reserve an OS-selected
loopback socket, generate a random session secret, and start the backend with
the still-bound socket inherited through the Phase 2 handoff in Section 8.
Publish the endpoint to the frontend only after the owned backend confirms
listening and authenticated readiness succeeds. On quit, request graceful
shutdown and ensure the child process and its socket handles have closed.

The backend must never bind to all network interfaces in ordinary desktop mode.
Only the later, explicitly enabled mobile companion mode may expose a separate
authenticated service to the local network.

### 3.2 iPhone companion

```text
iPhone companion
        │ paired, authenticated local connection
        ▼
Mac companion service
        │
        ▼
Existing local backend and SQLite data
```

The first iPhone version will require the Mac application to be open and both
devices to be on the same trusted network. A hosted multi-user backend can be
introduced later without replacing the iPhone interface because both clients
will use a documented API boundary.

## 4. Mac feature scope

### Included

- Daily Scanner, including progress, filters, sorting, column visibility,
  resizing, and saved state.
- Candidates list and maximized chart views.
- Fundamentals analysis and validation.
- Watchlists, Journal, and Planned Trades.
- Reports, PDF generation, preview, save, and open actions.
- Backtesting and portfolio features already exposed by the application.
- Application settings and Massive connection management.
- The approved AI Analysis feature when that plan is implemented.
- Current cross-page ticker selection and navigation behavior.
- Existing browser-development mode for engineering and troubleshooting.
- Local logs and a user-accessible diagnostics export.

### Explicitly excluded from the first Mac milestone

- App Store submission.
- Cloud accounts, cross-device synchronization, or subscriptions.
- Automatic trade execution or brokerage integration.
- Multi-user operation on one backend.
- Running the scanner when the Mac is shut down.
- Automatic background launch at login.
- Automatic self-update in the first development build.
- Any collection of a user's Massive account password.

## 5. iPhone companion scope

### Included in the first iPhone milestone

- Mobile dashboard with latest scan status and a concise result summary.
- Candidate browsing and selection.
- Mobile-friendly price charts with touch pan and zoom.
- Fundamental summary, valuation, quality, validation, and risk findings.
- Watchlist selection, creation, addition, and removal.
- Saved reports, AI analyses, recommendation revisions, and citations.
- Starting a scan on the Mac and monitoring its progress.
- Notifications while the app is active and local notifications after a
  completed status refresh.
- Navigation between a selected ticker's chart and fundamentals.
- Secure pairing, connection status, explicit unpairing, and revocation controls.

### Simplified or excluded from the first iPhone milestone

- Desktop-style wide tables and arbitrary column resizing.
- Large filter panels; mobile will use compact filter sheets.
- Server paths, worker counts, provider diagnostics, and database controls.
- Complex report-authoring controls.
- Running FastAPI, Python worker pools, or full scans on the phone.
- Scanning while disconnected from the Mac.
- Remote access outside the trusted local network.

These boundaries must be implemented as a feature-capability map, not scattered
screen-width checks. A mobile route must either have a purposeful mobile layout
or be absent from mobile navigation.

## 6. Repository and build structure

Add the Tauri project beneath the existing UI so the browser build remains
available:

```text
scanner/
├── src/scanner/                 Python application
├── ui/
│   ├── src/                     shared React application
│   ├── src/platform/            runtime capabilities and adapters
│   ├── src/layouts/             desktop and mobile navigation layouts
│   └── src-tauri/               Tauri Mac and later iOS hosts
├── packaging/
│   ├── desktop_sidecar.spec     repeatable Python sidecar definition
│   ├── entitlements/            signing entitlements
│   └── scripts/                 build and verification helpers
└── tests/
    └── packaging/               installed-application smoke tests
```

Use the existing frontend for both browser and Tauri builds. Introduce a small
runtime adapter instead of calling Tauri APIs directly throughout the React
component tree. Browser tests must remain able to substitute the adapter.

Establish these boundaries while implementing Phases 1 and 2:

- Keep path resolution, file actions, credential controls, connection setup,
  and runtime capabilities behind typed adapters. Pass resolved paths from the
  native host to Python; avoid independent, conflicting path conventions.
- Introduce thin repository interfaces for business records as those records
  are migrated. Keep SQLite implementations; an ORM rewrite is not a Phase 1
  prerequisite.
- Define the application API under `/api/v1` with stable record identifiers,
  request/response schemas, error codes, job statuses, and idempotency keys for
  operations that create work. Define ordinary watchlist mutation/retry contracts
  under Section 6.3 as well; job idempotency alone does not cover them. Generate
  or validate TypeScript types against backend schemas and add contract tests
  in Phase 2.
- Preserve current browser routes and `/api` consumers through a documented
  compatibility adapter during migration. Keep desktop lifecycle endpoints
  separate and advertise API versions/capabilities during connection setup.
- Use report IDs rather than repository paths in API contracts. Authenticated
  downloads must go through the API/file adapter; never place bearer tokens in
  URLs to make a browser link or PDF preview work.
- Compile desktop process management and credential integration only into the
  desktop target. The iOS target must neither bundle nor attempt to start Python.

The Python sidecar will initially use a PyInstaller one-directory build rather
than a one-file executable. This reduces startup delay and makes native Python
dependencies easier to diagnose. The packaged sidecar must contain Python,
FastAPI, Uvicorn, report fonts/assets, certificate roots, and all imported
native libraries. Nuitka is the documented fallback only if a required native
dependency cannot be packaged reliably with PyInstaller.

Before Phase 2A, validate a minimal packaged production workflow and the intended
bundle layout for signing, as specified in Phase 2. Inventory nested executables,
frameworks, and native libraries; preserve required symlinks and sign nested code
before its containing bundle. Review the Phase 0 `Contents/Resources/sidecar`
layout and adjust code/resource placement when required. Do not assume that
successful unsigned launch proves release signing will work. Apple documents
the distinction between nested code and ordinary resources in its
[code-signing guidance](https://developer.apple.com/library/archive/technotes/tn2206/_index.html).

### 6.1 Development and distribution signing evidence

Keep these profiles and their results distinct:

| Profile | Required evidence | Gate |
| --- | --- | --- |
| Local development integrity | Complete nested-code inventory, inside-out signing, strict bundle verification, and packaged scan/PDF/reopen plus native-library loads; ad-hoc signing is allowed | Mandatory Phase 2 evidence before Phase 2A; not production-hardening or distribution acceptance |
| Apple-issued hardened-runtime test | Record certificate type/Team ID, hardened-runtime flags, and reviewed per-executable entitlements; run the packaged workflow and native loads under that exact profile | Run early in Phase 2 when a suitable identity is available; otherwise record as deferred, not passed |
| Distribution | Developer ID signature, reviewed production entitlements, hardened-runtime workflow, notarization, and clean-Mac Gatekeeper acceptance for the delivered artifact | Mandatory Phase 4 distribution gate, including when an earlier development-certificate test passed |

Do not treat ad-hoc or self-signed success as equivalent to Apple-issued
production signing. PyInstaller documents Team-ID/library-validation failures
with self-signed identities under hardened runtime in its
[macOS signing guidance](https://pyinstaller.org/en/stable/feature-notes.html#macos-binary-code-signing).
Keep development and distribution configuration separate. Do not disable
production library validation or add broad entitlements merely to pass a local
test; any required exception needs a documented dependency-specific reason and
verification under the production profile. If no suitable identity is available
in Phase 2, explicitly carry the unverified hardening risk into Phase 4 rather
than blocking Phase 2A on a production-equivalence claim a local test cannot make.

### 6.2 Local iPhone provisioning prerequisites

Before the Phase 5 physical-device connection proof:

- Record the chosen Apple signing team, stable bundle identifier, Xcode/iOS SDK,
  required capabilities, provisioning method, and who owns renewal. Use a
  Personal Team for a short-lived proof if suitable; paid program enrollment
  requires the user's approval and must not be inferred from this plan update.
- Document Apple Account setup in Xcode, device trust/registration, signing
  configuration, and enabling Developer Mode on the test phone. Verify that the
  selected team can provision the required capabilities on the actual device.
- Disclose that Personal Team provisioning profiles expire after seven days
  and require rebuilding/reinstalling. A development install is not a permanent
  release mechanism. Record the renewal procedure for the chosen method, and
  select a sustainable local-installation approach before Phase 6 acceptance.
- Test renewal and an in-place signed upgrade/reinstall without first deleting
  the app: intended UI state, cached data policy, and pairing credentials must
  survive when the signing identity/access group remains compatible. Document
  uninstall and signing-team changes separately; do not promise preservation
  when those operations change the app's storage or Keychain access.

Apple documents [Personal Team provisioning and expiration](https://developer.apple.com/help/account/basics/about-your-developer-account)
and [Developer Mode](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device).
These local testing prerequisites belong to Phases 5 and 6, not just the later
public-distribution gates. No enrollment or device-setting change is authorized
merely by documenting them here.

### 6.3 Watchlist mutation, retry, and conflict contract

Define this contract in Phase 2 and implement it across shared business services
and browser/desktop clients before enabling mobile watchlist writes in Phase 5.
It covers create, rename, delete, and item addition/removal or updates. It does
not introduce cloud synchronization or permit creating new edits while offline.

- Give each user command a client-generated operation ID. Keep that ID and its
  original payload while the outcome is unknown, including reconnect/relaunch;
  a retry must not silently become a new command with a new ID. Keep this bounded
  in-flight command record free of bearer tokens and provider credentials.
- Authorize every request before looking up its result. Persist an operation
  receipt, request digest, and outcome alongside the affected business records
  in the same SQLite transaction as the mutation. Matching completed retries
  return the recorded outcome without another write; reusing an ID with a
  different target, payload, or precondition returns a conflict. Concurrent
  duplicates and backend restart must preserve the same guarantee.
- Give watchlists a server-issued revision. For a new command affecting an
  existing watchlist, check the expected revision and apply the mutation/revision
  increment atomically. Return an explicit stale-edit conflict for refresh and
  user resolution, not a silent overwrite. Deduplicate completed retries before
  re-evaluating their original revision; current authorization still applies.
  An `If-Match`/ETag contract can express this precondition, as described in
  [HTTP conditional-request semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1).
- Specify a server-enforced, bounded retry window and retain receipts for at
  least that window; an expired operation must not become a fresh write merely
  because its receipt has been pruned. On reconnect, retry only the original
  command within that window. After expiry or an unresolved outcome, refresh
  server state and require user confirmation before issuing a new command.
  Invalidate old retry intent when unpairing/re-pairing, restoring a backup, or
  switching data roots. Temporary connection loss alone is not such a reset.
- Apply the same service rules to every writer, including compatibility routes.
  Update browser/desktop clients with the contract; unsupported writers must get
  an actionable compatibility response rather than bypass revision checks.
  Show pending, confirmed, and conflicted outcomes distinctly, and refresh after
  a confirmed retry because another device may have changed the record since.
- Test response loss after commit, retry after backend restart, concurrent
  duplicate submissions, reused IDs with different payloads, stale revisions,
  and expired retries. In particular, phone add succeeds -> response is lost ->
  Mac removes the item -> phone retries the original command must not re-add it.

## 7. Application data and migration

Normal packaged runtime must use the resolved application directories for
mutable data, never the application bundle or Git repository. An explicit
migration is the narrow exception: the user may select legacy source data inside
the repository for read-only import under Sections 7.1 and 7.2. Do not modify
source business records, migrate their schemas, create missing source secrets or
keys, or leave runtime repositories pointing at the source after import. The
limited SQLite snapshot bookkeeping described in Section 7.2 still applies.

Resolve standard macOS directories through platform APIs, using one consistent
application subdirectory. The intended layout is:

```text
~/Library/Application Support/Swing Scanner/
├── data/             SQLite databases
├── reports/          generated report source files
└── backups/          migration backups

~/Library/Caches/Swing Scanner/
├── market/           rebuildable market data
├── sec/              rebuildable SEC responses
└── exports/          temporary exports and previews

~/Library/Logs/Swing Scanner/
└── scanner.log
```

Only data that can be regenerated belongs in Caches; immutable inputs needed to
reproduce a saved analysis remain with its durable records. User-selected exports
go to the destination chosen in a native Save dialog. Cache deletion must not
remove business records or saved reports. This follows Apple's
[directory guidance](https://developer.apple.com/library/archive/documentation/FileManagement/Conceptual/FileSystemProgrammingGuide/FileSystemOverview/FileSystemOverview.html).

### 7.1 Paths, records, and browser migration

- Centralize all paths behind one application-path service.
- Support explicit data, cache, report, and log path overrides in development
  and tests.
- Remove assumptions that the current working directory is the repository.
- Give every persisted schema an explicit version and forward migration.
- Inventory filesystem data and browser storage separately. Classify every
  relevant key as durable business data, UI preferences, rebuildable state, or
  a secret. Planned Trades currently use `localStorage` and must be included in
  essential-data migration.
- Store durable business records, including Planned Trades, in SQLite behind
  the application API. Keep ordinary display preferences in versioned,
  namespaced `localStorage`; only explicitly disposable preferences may be
  discarded on an incompatible version.
- Add an explicit export in the existing browser application and import in the
  desktop application. The export runs in the original browser/origin, since
  a native WebView does not inherit browser storage. Do not scrape browser
  profile files or assume that copying SQLite files migrates browser records.
- Version the export format, validate types and size limits, exclude secrets,
  and include source identifiers, record counts, and digests. Preview imports,
  assign stable record IDs, and make re-import idempotent. Malformed input and
  duplicate imports must not damage existing records.
- Migrate the browser UI to the same business-record API while preserving an
  export of its old data. Remove obsolete browser business-data keys only after
  successful reconciliation and an explicit user cleanup action.
- Provide an optional first-run import from the existing local scanner data.
- Treat an explicitly selected repository source as import input only. Validate
  and snapshot it without initializing or migrating the original store; perform
  schema changes in the staged destination. A missing/corrupt source or key must
  produce a recoverable error, not trigger creation of replacement source files.
- Preview what will be imported and create a backup before changing the new
  application database.
- Never silently delete the original development data after import.
- Exclude caches and temporary exports from essential-data backups.

### 7.2 Backup, restore, and import gate

Complete this procedure in Phase 1 before modifying existing application paths
or importing data into an active destination:

1. Inventory all databases, browser exports, reports, configuration, and the
   legacy credential database/key pair. Record their owners, schema versions,
   sizes, and relationships; do not expose secret contents in the manifest.
2. Pause mutations and stop or drain active jobs during the coordinated backup.
   Prevent new browser edits while capturing its business-data export. Acquire
   the exclusive destination ownership lock in Section 7.3 before opening target
   databases or touching schemas. A migration-only mutex is not sufficient.
3. Snapshot SQLite databases with the SQLite backup API or an equivalent SQLite
   snapshot facility. Never copy a live `.db` file alone or independently copy
   its WAL files. Keep the write pause while collecting related database and
   report snapshots so the backup represents a consistent application state.
4. Copy durable reports, configuration, and the browser export into a protected,
   versioned backup directory. Back up the legacy credential database together
   with its matching encryption key in a separately encrypted recovery archive;
   never store that archive's recovery secret alongside it. Verify that recovery
   material is available before declaring credential backup complete. Exclude
   credentials and key files from ordinary data exports and diagnostics.
5. Record checksums and counts, run SQLite integrity and foreign-key checks on
   the snapshots, and restore into a separate temporary data root. Reconcile
   business records and report references. Verify legacy credential decryption
   without printing values or making provider requests.
6. Import into a staged destination, apply versioned migrations, and reconcile
   counts/IDs before activation. Retain the previous destination and source
   backup for rollback. A failed or interrupted import must leave the active
   destination usable and the original development data intact.
7. Record the successful restore exercise and recovery instructions. Before an
   upgrade migration, snapshot the active destination again; older application
   versions must refuse incompatible newer schemas and use the documented
   rollback/restore path instead of attempting an implicit downgrade.

Keep ownership for the entire destination operation, including activation and
recovery after an interrupted activation. Reserve a restore-in-progress marker
outside the payload being restored. Once companion support exists, every restore
or rollback from backup must also apply Section 8's pairing-invalidation policy
before the companion listener can start. Restoring business data must never
restore an old phone's authorization. Phase 1 establishes this restore boundary;
Phase 5 implements and tests the companion-specific invalidation.

The source's business records must remain unchanged. SQLite may acquire locks
or maintain journal bookkeeping while producing a snapshot; this is not a data
migration. A completed copy without a restore exercise does not satisfy the gate.
The supported snapshot mechanism is described in the
[SQLite backup documentation](https://www.sqlite.org/backup.html).

### 7.3 Exclusive data-root ownership (Phase 1)

- Before opening any active database, the backend acquires an OS-backed exclusive
  ownership lock keyed to the canonical data root. Hold it for the lifetime of
  all database access, not just schema changes. Keep its lock file in a stable
  location outside directories replaced during import/restore; never delete or
  replace that file to bypass a held lock.
- All application entry points that access the same root must follow this
  protocol: packaged backend, browser-development backend, CLI, and migration,
  import, restore, and backup tools. Other processes use the owning backend's
  API, operate on an isolated root, or fail with an actionable in-use message.
  Explicit path overrides must not bypass ownership through path aliases.
- Run maintenance through the owner in an exclusive maintenance state, or stop
  the owner and let a standalone tool acquire the same lock. Drain work and close
  affected database handles before staged activation. Record enough activation
  state to recover one consistent database/report set after interruption; do not
  expose a partially activated destination to requests.
- The process that accesses SQLite must retain ownership even if the native host
  exits; a new host cannot start data access until the old backend has stopped
  and released ownership. Phase 2 adds parent-loss cleanup and window focusing,
  but database exclusion is already a Phase 1 requirement. PID/lock-file existence
  alone is not proof of a live owner or permission to take over.
- Stop legacy processes that do not implement this protocol before snapshotting
  their source. An application lock does not constrain arbitrary external SQLite
  tools; the coordinated source write pause in Section 7.2 still applies.
- Test simultaneous app launches, CLI/backend contention, launch during import
  or restore, equivalent path aliases, and termination before/during/after
  activation. Verify exclusion, recovery, and unchanged source business records.

## 8. Credential and local API security

### Provider credentials

- Store Massive and OpenAI API keys in macOS Keychain under application-scoped
  service names.
- Keep environment-variable overrides for development and managed installs.
- Add a one-time migration from the existing encrypted SQLite secret store.
- Verify a new credential before replacing a valid credential.
- Never return full secrets to the frontend, logs, diagnostics, or crash data.
- Provide explicit Replace, Test, and Disconnect actions.
- Never request or retain Massive or ChatGPT usernames and passwords.

In desktop mode, the Rust host owns Keychain access under stable service/account
identifiers. The frontend may submit a user-entered replacement and request
Test/Disconnect/metadata actions, but there must be no command returning stored
provider keys to JavaScript. Clear transient entry fields after submission.

Deliver credentials retrieved from Keychain to the owned Python sidecar through
a private inherited bidirectional channel with bounded messages and explicit
acknowledgements. Do not place those values in command-line arguments, URLs,
provider-key environment variables, shared files, stdout, or logs. Validate a
replacement through the backend before promoting it in Keychain; if persistence
or delivery fails, retain the prior working credential. Handle a locked Keychain,
denied access, application upgrade, replacement, and disconnect explicitly.
Environment overrides remain an explicit browser/development/managed-install
mode; they must not silently replace a desktop Keychain credential.

Legacy migration reads the selected encrypted source and its matching key,
validates decryption, writes to Keychain, and verifies readback. Provider
connectivity testing is a separate bounded check: an offline Mac must retain its
recoverable source rather than lose a credential. Exclude legacy secrets from
the active desktop business database. Preserve the original browser installation
and protected recovery archive; any subsequent source cleanup is an explicit
user action. The no-SQLite-secrets acceptance criterion applies to the active
desktop store, not to those retained legacy sources.

### Sidecar API

- Bind to `127.0.0.1` only in normal desktop mode.
- Bind an OS-selected port at launch and preserve socket ownership through the
  handoff below; do not probe a free port, release it, and later bind by number.
- Generate a cryptographically random bearer secret on every application
  launch and pass it to the backend through the child-process environment.
- Require the secret for all application data and mutation endpoints.
- Pass the base URL and secret to the frontend in memory; do not persist the
  per-launch secret.
- Use an allowlist for browser-development origins and do not use unrestricted
  production CORS.
- Add request-size limits and retain existing input validation.
- Redact authorization headers, keys, and sensitive query parameters from logs.

#### Gap-free socket handoff (Phase 2)

- The host binds `127.0.0.1:0` and passes the still-bound socket descriptor only
  to the owned sidecar. The child serves that socket rather than binding the
  numeric port again. Keep the host's descriptor open until the child has its
  inherited handle and confirms listening over the private control channel;
  then close the host's duplicate. There must be no unowned interval.
- Use the inherited control channel already required for host/sidecar integration
  to correlate startup acknowledgement with the current child/session. Only then
  perform authenticated health checks and publish the endpoint to the WebView.
  Use an absolute startup deadline and bounded individual requests, not just a
  retry count. Failed startup closes handles, reaps the child, and does not
  publish a usable runtime configuration.
- On backend exit/restart, retire the old frontend connection configuration and
  cancel its requests. A replacement backend gets a new session secret and a
  newly owned socket through the same handoff; do not blindly reuse an endpoint.
- Test a competing bind throughout delayed startup/handoff, failure before and
  after acknowledgement, forced child exit, restart, and handle cleanup. The
  competing process must never acquire the reserved socket while it is in use.

Uvicorn supports serving an inherited socket descriptor, as documented in its
[deployment guidance](https://www.uvicorn.org/deployment/#supervisor).
Phase 0's free-port probe is historical proof behavior, not evidence that this
Phase 2 ownership requirement is already implemented.

### WebView and native-command security

Complete these requirements in Phase 2 before enabling the full desktop UI:

- Set a production Content Security Policy for bundled scripts/styles, the
  required Tauri IPC endpoints, and the loopback API connection. Support the
  dynamically chosen API port without allowing arbitrary remote connections;
  document any necessary loopback-only wildcard and test the policy in a release
  WebView. Keep development allowances in development configuration.
- Allow only required Tauri commands and filesystem scopes for each window.
  Enforce validation and authorization inside custom commands as well as in
  capability configuration; remote pages must never acquire native privileges.
- Restrict in-app navigation to bundled application routes. Open explicitly
  permitted external HTTP(S) links with the platform adapter, reject unsafe URL
  schemes, and never forward app tokens or provider credentials to those links.
- Treat imported data, provider text, reports, citations, and AI output as
  untrusted. Escape plain text; use a tested sanitizer and safe-link policy when
  rendering Markdown/HTML. Do not execute returned scripts or arbitrary HTML.
- Retain authentication on every business/file endpoint, explicit origin/host
  validation, request-size limits, and authorized file resolution. Test allowed
  native origins, rejected foreign origins, missing/wrong tokens, malformed
  input, and path traversal. CORS is not a substitute for authentication.
- Exclude secrets from frontend persistence, errors, diagnostics, logs, and
  crash attachments. Add checks for both session tokens and provider keys.

Phase 0 currently has CSP disabled; that is not the intended production policy.
Tauri's protection must be explicitly configured, as described in its
[CSP documentation](https://v2.tauri.app/security/csp/).

### Mobile companion mode

Mobile access must be off by default. Enabling it will require an explicit Mac
setting and a pairing ceremony. Pairing will issue a revocable, device-specific
credential. The design must use encrypted transport, show connected devices,
allow immediate server-side revocation, and never reuse the desktop sidecar
session secret.

Establish this concrete transport/trust design in Phase 5 before mobile screens:

- Keep the ordinary desktop listener on loopback. Use a separate explicitly
  enabled companion listener and a restricted set of companion API operations;
  never expose desktop credential, arbitrary file, or shutdown controls to LAN
  clients. The Mac backend remains the only owner of its SQLite files.
- Advertise the companion using Bonjour on the enabled network and provide a
  manual-address fallback. Discovery supplies an address, not proof of identity.
- Establish a per-installation Mac TLS identity with private key material
  protected by macOS Keychain and accessed through the native transport boundary.
  Pair using a short-lived, single-use QR invitation containing a protocol
  version, endpoint, server public-key fingerprint, and random invitation secret,
  with confirmation on the Mac. Rate-limit attempts and invalidate expired/used
  invitations.
- Validate the pinned server identity before sending the invitation secret or
  device credential. Use a native networking adapter capable of enforcing this
  trust policy; prototype it rather than assuming WebView `fetch` alone is
  sufficient. Never implement a trust-all certificate exception.
- Issue a unique device credential and retain its verifier/revocation state on
  the Mac. Store the phone credential in iOS Keychain and keep it out of WebView
  storage. Device credentials identify a permitted companion, not an account
  with access to desktop settings or provider keys.
- On address/network changes, rediscover the same pinned identity. Certificate
  renewal retaining the pinned key may reconnect; a changed server key requires
  authenticated rotation or explicit re-pairing. Rotate device credentials with
  a bounded transition and invalidate previous credentials after acknowledgement.
- Revocation immediately rejects subsequent server requests, closes active
  companion sessions, and prevents authenticated reconnect with the old
  credential. Apply the distinct connection-loss, unpairing, and revocation
  states below; a network error alone must not delete pairing credentials.
- Validate iOS and macOS local-network permissions, Bonjour declarations,
  applicable ATS settings, denied permission, network changes, Mac sleep/wake,
  wrong certificates, expired invitations, and revocation on real devices.

Apple documents [server-trust evaluation](https://developer.apple.com/documentation/Foundation/performing-manual-server-trust-authentication)
and [local-network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy?changes=_9%2C_9).
The simulator does not validate local-network privacy behavior; it supplements
the physical-device checks and does not replace them.

#### Connection loss, unpairing, and revocation

| Event | Phone behavior | Mac authorization |
| --- | --- | --- |
| Temporary connection loss, Mac sleep, Wi-Fi change, or permission denial | Keep pairing credentials and unexpired read-only cache; show offline/permission status and retry safely against the pinned identity | Pairing is unchanged; loss of transport is not revocation |
| Explicit Unpair / Forget this Mac on the phone | Clear local credentials and cached content; require new pairing for future use | Request revocation if reachable; if unreachable or unacknowledged, disclose that server revocation is unconfirmed and direct the user to revoke the device on the Mac |
| Mac revokes a device, or a trusted server definitively rejects its pairing | On detection, clear local credentials/cache and require re-pairing; do not classify an ordinary timeout as revocation | Reject subsequent requests with the old credential and close its active sessions |

Use these labels consistently instead of an ambiguous Disconnect action. An
offline phone cannot receive immediate deletion instructions. Define a bounded
cache lifetime; reject expired content before display and purge on expiry while
running or at the next launch/resume before rendering it. Expiring cached content
does not itself revoke a still-valid pairing. Remote erasure while offline or
suspended is not promised.

#### Pairing authority after backup restoration

The supported restore policy is to require fresh pairing after activating any
backup or rollback snapshot; ordinary in-place upgrades without restoration do
not invalidate pairing unnecessarily.

- Under Section 7.3 ownership, durably mark restoration in progress outside the
  restored payload and stop the companion listener/sessions before activation.
- Invalidate existing device credentials and invitations, and discard restored
  pairing verifiers/authorization records before allowing companion traffic.
  Business-data import/export must never grant access from imported pairings.
- Leave companion access disabled after restoration until the user explicitly
  enables it and pairs devices again. Preserving a Mac TLS identity must not
  preserve the validity of old device credentials.
- Interrupted cleanup or inconsistent restoration state must fail closed: do not
  start the listener until recovery and invalidation have been verified. Keep
  the pending marker until that safe state is durably recorded.
- Prove that backup -> revoke phone -> restore backup -> restart still rejects
  the old credential, including interruptions around activation/invalidation.
  Also test restoration on a different Mac and repeat restoration of the same
  snapshot. Phone cache removal remains subject to detection/expiry, as above.

## 9. Desktop experience

### Window and navigation

- Preserve the full desktop navigation and existing routes.
- Restore window size and position while ensuring the window remains visible
  if monitor arrangements change.
- Set a practical minimum window size and retain horizontal table scrolling for
  narrower desktop windows.
- Keep the primary application menu fixed while content scrolls.
- Provide native menu items and keyboard shortcuts for common actions, reload
  only in development, diagnostics, and quit.
- In Phase 2, handle a second launch by focusing the existing window. Reuse the
  Phase 1 data-root ownership guarantee; database exclusion must not wait for
  the window-focusing feature.

### Files and reports

- Use native Save dialogs when exporting PDFs or data.
- Use native Open and Reveal in Finder actions for generated files.
- Generate reports in the application report directory before copying an
  export to the user's chosen destination.
- Clean temporary exports according to an explicit retention policy.

### Startup, errors, and recovery

- Display a branded startup state while the backend becomes ready.
- Distinguish backend startup, migration, port, credential, and data-corruption
  failures with actionable messages.
- Capture sidecar output into rotating local logs.
- Offer Retry Backend, Open Logs, and Export Diagnostics actions when startup
  fails.
- Attempt at most one automatic restart after an unexpected backend exit; do
  not enter an invisible restart loop.
- Preserve durable scan results and identify in-progress jobs interrupted by an
  application exit.

### Local job persistence and shutdown

Implement the common local job lifecycle in Phase 2 for scans, backtests,
report-generation work, and later AI jobs. The present thread executor and
in-memory registry may continue dispatching work, but SQLite becomes the durable
source of job identity, input snapshot/reference, status, progress, result
references, cancellation intent, timestamps, and errors. No external queue or
database server is required for this local lifecycle.

- Persist a queued job before execution. Use a client idempotency key and a
  uniqueness constraint to return the original job for duplicate submissions.
  Record input/version information needed to distinguish a retry from new work.
- Persist checkpoints at bounded intervals and at stage transitions; keep
  transactions short and outside provider/network calls. Define connection
  ownership, WAL/busy-timeout handling, and bounded write contention across jobs.
- On startup, reconcile unfinished jobs from a prior backend session as
  interrupted and show recovery actions. Restarting the backend must not
  automatically restart costly or non-idempotent work.
- Cancellation stops new work, records intent, and lets in-flight operations
  finish within a bounded deadline. On quit, reject new jobs, request
  cancellation/drain, persist the latest safe state, flush outputs, and close
  database connections. Use an initial 10-second backend grace deadline followed
  by a bounded forced-stop fallback, then reap the process and any owned workers.
- Own the backend independently of the WebView lifecycle. Handle host failure
  through parent-liveness detection; a backend that loses its owner must stop
  safely. Serialize restart requests and prevent a second backend from accessing
  the same active data root using the Phase 1 ownership protocol in Section 7.3.
- Define retry behavior per job type. Reuse completed checkpoints where valid;
  otherwise create an explicitly linked new attempt. A timed-out external
  request may already have completed, so reconcile uncertain results when the
  provider supports it and make potential repeat charges visible.
- Write reports to staged files and activate their durable references only
  after completion. Tests must cover quit, forced termination, relaunch, duplicate
  submission, interrupted output, and recovery without duplicate saved results.

Phase 2A reuses this common lifecycle while retaining the AI plan's per-stock
checkpoints, analysis history, retry rules, and interrupted-run behavior.

## 10. Mobile experience principles

- Use a bottom tab bar for Dashboard, Candidates, Watchlists, Reports, and More.
- Present ticker detail as the central mobile navigation object.
- Replace dense rows with summary cards and drill-down detail.
- Place filters and sort controls in sheets with active-filter counts.
- Use touch-sized controls and safe-area-aware layouts.
- Preserve the selected ticker, frequency, interval, filters, and appropriate
  page state across navigation and relaunch.
- Reuse the existing chart calculations while implementing touch-specific pan,
  zoom, crosshair, and entry interactions.
- Make temporary connection loss visible, retain pairing, and keep the last
  successfully loaded data as unexpired read-only cached content where safe.
- Do not represent a stale cached result as current; always show its timestamp.
- Apply the credential, bounded-cache lifetime, and revocation behavior in
  Section 8. Offline cached content is explicitly read-only and never authorizes
  a new server action.

## 11. Delivery phases

### Pre-implementation baseline

- Record the current Python test, React test, and production frontend build
  results before changing packaging or runtime behavior.
- Identify existing failures separately from Phase 0 regressions.
- Inventory mutable SQLite, reports, credentials and their encryption keys,
  caches, and browser-held business records that later phases must relocate.
- Create a recoverable backup of essential existing data before Phase 1 changes
  any application paths or performs an import. The Phase 0 proof of concept does
  not read or modify that data and therefore does not require an early copy.
- Record the target architecture and operating-system version for the first
  build.

Status:

- Test and build baselines have been captured.
- Phase 0 was tested on Apple Silicon with macOS 26.5.2. The minimum/current
  platform targets for subsequent work are defined in Section 2.1.
- The essential-data backup remains a required gate before Phase 1.

### Phase 0 — Packaging proof of concept

- Install and configure Tauri 2 in `ui`.
- Open the production React build in a native Mac window and render a dedicated
  Phase 0 readiness screen. Do not exercise repository-relative production data
  from this proof-of-concept screen.
- Build a PyInstaller one-directory Python sidecar containing an authenticated
  FastAPI health endpoint and smoke imports for NumPy, pandas, matplotlib, lxml,
  Pillow, certifi, and Uvicorn.
- Bundle the complete sidecar directory as a Tauri application resource so the
  packaged build does not depend on Python or the project virtual environment.
- Have Tauri own sidecar startup, captured output, readiness, retry, graceful
  shutdown, and bounded forced-shutdown fallback.
- Demonstrate an authenticated frontend health request on an automatically
  selected loopback port using a cryptographically random per-launch bearer
  secret that is held only in memory.
- Show useful starting, connected, dependency-version, and actionable failure
  states in the native window.
- Package and launch the proof from Finder on the target Apple Silicon Mac.

Exit criteria:

- `Swing Scanner.app` opens without Terminal or an external browser.
- One application process owns one backend child process.
- Quit leaves no orphaned backend process.
- No fixed development port is required.
- The WebView completes an authenticated request to the sidecar and an
  unauthenticated request is rejected.
- The packaged sidecar successfully imports the identified native-heavy Python
  dependencies.
- The proof continues to launch when ports 5173 and 8000 are occupied.
- The proof launches without the Git repository, Python executable, or virtual
  environment being available at runtime.

### Phase 1 — Filesystem and configuration readiness

- Complete the coordinated snapshot, browser export, protected credential
  recovery backup, and restore gate in Section 7.2 before changing existing
  paths or importing data. Use the Section 7.3 ownership protocol and staged import.
- Implement exclusive data-root ownership across backend and maintenance entry
  points before any active destination database is opened. Keep ownership across
  staged activation and recovery; reserve the restore marker outside its payload.
- Add the centralized application-path service.
- Route every database, cache, report, export, and log path through it.
- Remove working-directory and repository-relative runtime assumptions.
- Add migrations and development-path overrides.
- Inventory `localStorage` keys and implement explicit browser export/desktop
  import for business records, including Planned Trades. Persist those records
  through SQLite repositories; retain only versioned UI preferences in browser
  storage and preserve original data until verified cleanup is requested.
- Establish the path/file/runtime adapter interfaces and `/api/v1` schema
  conventions from Section 6 while preserving existing browser consumers.
- Remove personal developer information from production defaults, including the
  current hard-coded SEC contact identity; collect or configure an appropriate
  application identity during setup.
- Implement first-run existing-data import and backup.
- Permit only the explicit read-only repository-source migration exception in
  Section 7; normal application runtime must remain independent of that source.

Exit criteria:

- The packaged application runs from `/Applications` with the repository
  unavailable.
- All mutable files appear only in the expected user directories.
- A restored backup reconciles database records, reports, browser business
  data, and legacy credential decryption without exposing secrets.
- Existing data can be imported without changing source business records;
  failure, interruption, and duplicate-import tests preserve the active store.
- Explicitly selected repository sources can be imported without source schema
  changes or new credential/key files. Afterwards the app opens the imported
  records with the source repository unavailable; incidental snapshot bookkeeping
  is distinguished from source business-data mutation.
- Concurrent launches, CLI access, and import/restore cannot access a root owned
  by another process. Interrupted activation recovers a consistent store before
  requests are admitted; an orphaned live backend still excludes a second owner.
- Planned Trades exported from the original browser appear in the desktop
  business store with reconciled counts and survive application relaunch.
- Deleting rebuildable caches leaves business records and saved reports intact.
- Path overrides isolate tests, and unsupported schema versions are rejected
  with a documented restore path.

### Phase 2 — Secure desktop integration

- Implement host-owned Keychain storage, private credential delivery to Python,
  and recoverable legacy-secret migration as specified in Section 8.
- Add per-launch local API authentication, production CORS/CSP, restricted Tauri
  capabilities, safe navigation/content rendering, and secret-redaction checks.
- Add second-launch window focusing on top of Phase 1's data-root exclusion.
- Implement readiness, graceful shutdown, crash detection, and bounded restart.
- Implement Section 8's gap-free socket handoff and owned-child acknowledgement
  before publishing the frontend connection configuration. Replace Phase 0's
  probe/release/rebind sequence and test competing binds and failed startup.
- Persist the common local job lifecycle and implement cancellation, interruption
  reconciliation, idempotent submission, checkpoints, and bounded shutdown for
  existing jobs. SQLite holds durable state; worker threads only execute it.
- Complete desktop/browser API adapters, version/capability negotiation, and
  contract tests. Keep lifecycle/credential endpoints outside the companion API.
- Define Section 6.3's operation IDs, receipts, revisions, conflict responses,
  retry window, and client compatibility contract. Watchlist write enforcement
  and cross-client acceptance must pass in Phase 5 before mobile editing.
- Add rotating logs, redaction, and diagnostics export.
- Before Phase 2A, exercise a packaged workflow from Finder using isolated
  fixture data: load inputs, run a representative scan/calculation, persist its
  result, generate and open a PDF through the file adapter, quit, and reopen the
  saved result. Include the real production modules and report assets.
- Complete Section 6.1's local development-integrity profile: nested signing,
  strict bundle verification, native-library loads, and the packaged workflow.
  Record the identity and entitlements actually used. Run the Apple-issued
  hardened-runtime profile early if a suitable identity is available; otherwise
  record it as deferred with its remaining risk and Phase 4 owner. Do not report
  ad-hoc verification as production-hardening or Developer ID acceptance.

Exit criteria:

- Unauthorized local requests cannot read scanner data.
- Stored provider secrets do not appear in the active desktop SQLite store,
  frontend persistence, logs, diagnostics, URLs, or process arguments. Preserved
  legacy development sources and protected recovery archives remain explicitly
  separate. Locked/denied Keychain access and failed replacement are recoverable.
- The release WebView enforces CSP, remote content cannot invoke native commands,
  and unsafe navigation, imported content, and unauthorized file requests fail.
- Backend failures produce a visible recovery screen.
- No process can claim the reserved socket during handoff. Only the acknowledged
  owned backend's ready endpoint reaches the frontend, and failed/restarted
  sessions leave neither published stale configuration nor leaked socket handles.
- Queued/running jobs survive as recoverable records after forced termination;
  duplicate submission creates no duplicate job, and completed checkpoints are
  retained. Quit obeys the grace deadline and leaves no backend/worker process.
- The packaged scan/PDF/persistence workflow passes with the repository and
  external Python unavailable. Local bundle-integrity checks pass; the distinct
  Apple-issued hardened-runtime and distribution checks are either evidenced
  under their actual profiles or explicitly deferred to Phase 4 per Section 6.1.
- Contract tests pass for both browser and desktop adapters. These Phase 2 gates
  must pass before beginning AI implementation.

### Phase 2A — AI Analysis implementation

Implement the separately approved `AI_ANALYSIS_IMPLEMENTATION_PLAN.md` after
the application-path and security foundations exist and before Phase 3 full
feature acceptance. This prevents the AI feature from being built around
browser-owned backend assumptions or credentials that must immediately be
migrated.

- Implement the approved AI analysis schema, jobs, watchlist snapshots,
  rankings, follow-up conversation, recommendation revisions, refined
  watchlists, reports, and saved UI state.
- Use the centralized paths established in Phase 1.
- Use macOS Keychain integration and credential-resolution behavior established
  in Phase 2.
- Extend the Phase 2 job lifecycle with the AI plan's per-stock progress,
  interrupted analysis recovery, cost-aware retries, and durable result history.
- Keep durable analysis and conversation history in local SQLite.
- Make OpenAI calls through the packaged backend, never directly from React.
- Include AI routes and workflows in the Phase 3 packaging and acceptance
  matrix.

Exit criteria:

- The separate AI Analysis plan's definition of done is satisfied in browser
  development mode.
- AI credentials, history, jobs, and reports use the desktop-ready services
  established in Phases 1 and 2.
- Phase 3 can validate the complete AI workflow inside the packaged Mac app.

### Phase 3 — Full feature packaging

- Exercise and correct every existing route inside the Tauri WebView.
- Replace browser-only file behavior with platform adapters and native dialogs.
- Verify reports, charts, navigation, saved state, workers, and long scans.
- Ensure background jobs keep running while the application window is visible,
  minimized, or hidden, but stop safely on full application quit.
- Implement app menu, icons, metadata, About, and diagnostics screens.

Exit criteria:

- The packaged application passes the complete functional acceptance matrix.
- A normal user can configure Massive, run a scan, examine a candidate, create
  a watchlist, generate a report, and reopen the saved state without Terminal.

### Phase 4 — Local Mac release

- Produce a development application for immediate personal use.
- Add repeatable release build scripts and version stamping. Pin dependencies,
  record source revision, toolchain/SDK versions, target architectures, and
  build inputs. Produce per-artifact SHA-256 checksums and archive the exact
  delivered files with the manifest and signing/notarization evidence.
- Complete the Section 6.1 distribution profile, including any deferred
  hardened-runtime checks under the actual Developer ID identity and reviewed
  production entitlements. Sign and notarize before sharing with other Macs.
- Create a DMG with installation instructions.
- Add update-check capability only after a trusted release host and signing
  process exist; updates remain user-approved.
- Test clean install, upgrade, rollback from backup, and uninstall guidance.
- Verify the minimum/current macOS matrix in Section 2.1, including all native
  dependencies; newer-OS development builds alone do not prove the minimum.

Exit criteria:

- The delivered distribution artifact passes strict signature verification,
  the production hardened-runtime workflow, notarization, and Gatekeeper on a
  clean supported Mac. A successful local development profile cannot waive these
  checks. Personal development use may precede them but is not distribution
  acceptance or full Phase 4 completion.
- Upgrade preserves user data and credentials.
- A clean build can reproduce the documented procedure and pass the same
  acceptance checks. The exact delivered artifacts and their checksums are
  archived. Timestamped signatures/notarization may change bytes between builds;
  byte-for-byte identity of independently signed artifacts is not required.
- The advertised OS/architecture support matches recorded acceptance evidence.

### Phase 5 — Mobile connection proof and shared foundation

- Confirm the minimum iOS decision and record actual device/OS availability in
  Section 2.1's matrix. Complete Section 6.2's signing/provisioning prerequisites
  on the chosen physical phone before attempting the connection proof. Record
  missing minimum-version hardware coverage and its resolution plan explicitly.
- Extend the versioned API contract, runtime adapters, and capabilities already
  established in Phases 1 and 2; add mobile-specific capability negotiation and
  API mismatch behavior.
- Before mobile screen implementation, create a minimal Tauri iOS connection
  target and verify Section 8's discovery, pinned TLS identity, one-time pairing,
  device credentials, credential rotation, and revocation design against the Mac.
  Keep all desktop process-startup code excluded from the iOS target.
- Use a physical iPhone 15 or newer and the OS targets in Section 2.1 for the
  connection proof. Test both Mac and iPhone local-network permission behavior,
  invalid trust, expired invitations, address changes, and sleep/wake. Demonstrate
  temporary-loss recovery without deleting pairing or unexpired cached data.
- Implement Section 8's restore-triggered pairing invalidation at the Phase 1
  restore boundary. Verify revocation survives restoring an older snapshot and
  restarting, including an interrupted restore, before enabling companion use.
- Add mobile runtime capabilities and responsive layout layers after that proof.
- Extract reusable ticker detail, chart, fundamentals, watchlist, report, and AI
  components without regressing desktop behavior.
- Add the Mac mobile-companion setting, restricted companion API routes, and
  connected-device/revocation controls using the verified transport design.
- Implement Section 6.3's shared watchlist mutation service and update all
  supported writers, including browser/desktop compatibility paths. Prove lost-
  response retries and stale-edit conflicts before enabling mobile editing;
  the single data-root owner does not serialize users' read/edit intentions.
- Create iPhone wireframes and a route-by-route capability matrix.

Exit criteria:

- Shared components have browser tests.
- Desktop behavior remains unchanged.
- The mobile scope is represented explicitly in navigation and capabilities.
- The physical-device connection proof passes before mobile screens begin;
  Bonjour discovery never substitutes for server identity verification.
- The signing team, profile expiration/renewal procedure, device setup, and
  tested hardware/OS combinations are recorded. Any matrix gaps remain visibly
  unpassed; broader compatibility acceptance remains a Phase 6 requirement.
- Revocation closes active sessions and blocks subsequent server access;
  offline cache expiration/purge behavior is specified and tested separately.
- Unpairing, temporary loss, and revocation follow the separate Section 8 states.
  Restoring a pre-revocation backup cannot reactivate any old pairing credential.
- The iOS target builds without a Python sidecar or desktop-only commands.
- Watchlist writes cannot duplicate/replay an acknowledged effect or silently
  overwrite a stale revision. The add/lost-response/remove/retry scenario in
  Section 6.3 passes across Mac and phone API clients before mobile editing.

### Phase 6 — Locally installed iPhone companion

- Extend the minimal Tauri iOS target proven in Phase 5.
- Implement mobile navigation and layouts.
- Add iOS local-network disclosure and permission handling.
- Implement pairing, connection recovery, credential storage in iOS Keychain,
  and device revocation from the Mac.
- Implement the included mobile feature set and read-only cached states.
- Use the iOS Simulator for repeatable UI/layout tests and install on registered
  physical iPhone 15+ devices through Xcode for trust, permissions, pairing,
  revocation, Keychain, and the approved minimum/current OS matrix. Resolve gaps
  through Section 2.1; simulator success cannot satisfy physical-device gates.
- Complete Section 6.2's renewal and in-place upgrade/reinstall tests. Record a
  user-accepted sustainable provisioning approach and its renewal obligations;
  do not treat an expiring development profile as a permanent installation.

Exit criteria:

- The iPhone can pair with the Mac without exposing the desktop API publicly.
- Selected-ticker navigation remains consistent across mobile screens.
- A scan can be started and monitored while the Mac performs the work.
- Mobile watchlist editing uses Section 6.3's command/revision contract and shows
  unknown outcomes and conflicts clearly. Reconnection never blindly replays
  uncertain writes or creates new offline edits.
- Temporary connection loss preserves pairing and unexpired read-only cache;
  reconnect does not require re-pairing. Explicit unpairing and server revocation
  follow Section 8, including unconfirmed server revocation when unpairing
  offline. Immediate remote erasure while offline is not promised.
- Restoring or rolling back Mac data invalidates old phone authorizations before
  companion traffic resumes. Ordinary in-place upgrades and provisioning renewal
  preserve valid pairing/state under a compatible identity.
- Physical installation, documented renewal, and in-place upgrade/reinstall
  pass; uninstall and signing-team changes have explicit recovery instructions.
- The hardware/OS matrix in Section 2.1 passes and unsupported API versions
  produce an actionable compatibility message.

### Phase 7 — Optional public distribution architecture

This phase requires a separate approval before implementation:

- Decide whether to retain Mac-hosted companion access or deploy a cloud
  backend for access away from home.
- If a cloud backend is approved, select the hosted database using Section 16
  (PostgreSQL is the recommended default), then execute its provisioning,
  migration, and data-ownership gates. Neither PostgreSQL nor MariaDB is a
  prerequisite for Phases 0 through 6 or a replacement for local SQLite.
- If synchronization is included, implement and verify Section 16.8 before
  cutover. Database import alone does not provide synchronization or conflict
  handling between local and hosted records.
- Confirm Massive permits the intended bring-your-own-account integration and
  data displays in a commercial third-party application.
- Complete financial-services legal review of screening, ranking, and AI
  recommendations.
- Establish privacy policy, terms, support, data deletion, and retention.
- Add accounts, synchronization, durable cloud jobs, subscriptions, and StoreKit
  only if the approved product model requires them.
- Complete TestFlight and App Store submission work.

This phase must not be allowed to complicate or delay the local Mac milestone.

## 12. Testing and quality plan

### Automated coverage

- Preserve Python unit and API tests in normal development mode.
- Preserve React component, state, chart, and route tests.
- Add application-path and migration tests using temporary directories.
- In Phase 1, test ownership across backend/CLI/maintenance entry points,
  simultaneous launches, aliased paths, and interrupted destination activation.
- Add browser business-data export/import, repeated import, malformed input,
  coordinated backup/restore, credential recovery, and migration interruption
  tests. Verify restored records and report references, not just file existence.
- In Phase 1, test explicit repository-source import, missing/corrupt source
  material without source initialization, and post-import source independence.
- Add local API authentication and secret-redaction tests.
- Add production CSP, Tauri command-scope, navigation, untrusted-content,
  authorized-download, and Keychain failure/replacement tests.
- Add sidecar command, startup timeout, crash, restart, and shutdown tests.
- In Phase 2, test reserved-socket handoff against a competing bind, acknowledgement
  timeout/failure, endpoint publication, restart, and descriptor cleanup.
- Add durable job submission, checkpoint, cancellation, crash reconciliation,
  duplicate retry, parent-loss, worker cleanup, and shutdown-deadline tests.
- Add packaged-resource checks for certificates, fonts, templates, and native
  Python libraries.
- Add platform-adapter tests with browser and Tauri implementations.
- Add versioned API/schema contract tests in Phase 2, then mobile negotiation
  tests in Phase 5. Keep compatibility checks for existing browser consumers.
- Add mobile capability and state-restoration tests before the full mobile
  feature build in Phase 6; the minimal connection target is built in Phase 5.
- In Phase 5, test temporary loss versus explicit unpairing/revocation, and
  backup-before-revocation followed by restore/restart. Include interrupted
  pairing invalidation, repeated restore, and restore onto a different Mac.
- In Phase 5, test watchlist mutation receipts, lost responses, duplicate delivery,
  payload mismatch, stale revisions, retry expiry, and invalidated retry intent
  after unpair/restore/data-root changes. Cover browser/desktop/phone writers and
  ensure a retried old add does not undo a subsequent removal.
- Automate the small packaged scan/PDF/reopen workflow before Phase 2A and keep
  it as a regression check through release. Record minimum-OS native-library
  checks and separate results/deferred gates for each Section 6.1 signing profile.

### Mac acceptance matrix

- First launch with no prior data.
- Import from the current development installation.
- Import Planned Trades from the original browser origin and reconcile them
  after relaunch; verify that the original export/source remains recoverable.
- Restore a coordinated backup and recover from failed/interrupted migrations.
- Race a second app/CLI launch against import/restore and verify data-root
  exclusion. From Phase 5, verify restore/rollback does not revive revoked phones.
- Launch with ports 5173 and 8000 already occupied.
- Launch, minimize, restore, close window, and full quit.
- Relaunch after a forced backend termination.
- Quit during an active scan/report, interrupt the host, and retry a duplicate
  job request; verify durable recovery and no orphaned workers or duplicate data.
- Run each scanner strategy, including a long fundamentals scan.
- Sort, filter, resize, auto-fit, hide, and restore result columns.
- Traverse candidates in the maximized chart.
- Navigate selected tickers among Scanner, Candidates, Fundamentals, and
  Watchlists.
- Create, export, open, and reveal every PDF report type.
- Configure, replace, test, and remove provider credentials.
- Exercise locked/denied Keychain access, offline migration, failed replacement,
  and credential access across signed application upgrades.
- Upgrade over an older application version without losing user data.
- Run with the network unavailable and recover after connectivity returns.
- Test the minimum/current OS and architecture targets from Section 2.1.

### iPhone acceptance matrix

- First pairing, reconnection, revocation, and re-pairing.
- On physical devices, reject wrong server keys, expired/replayed invitations,
  revoked credentials, and unsupported API versions; exercise key rotation and
  rediscovery without weakening trust.
- Mac unavailable, Mac sleeping, network changed, and permission denied states.
- Restore transport after those temporary failures without losing pairing or
  unexpired cache. Test explicit unpairing online/offline separately from Mac
  revocation, and verify the offline unpairing UI does not claim confirmed
  server-side revocation.
- Touch chart pan and zoom on supported frequencies.
- Selected ticker and filter state across navigation and relaunch.
- Start and monitor scanner progress.
- Add/remove watchlist items with interrupted responses and concurrent Mac edits;
  verify receipt replay, conflict UI, and refresh without resurrecting removals.
- Review fundamentals, watchlists, reports, and AI history.
- Validate readable layouts with Dynamic Type and common phone sizes.
- Cover the recorded physical iPhone 15/newer-model combinations and confirmed
  minimum/current iOS matrix from Section 2.1. Record unavailable tests as gaps,
  not passes; do not infer network-privacy acceptance from simulator tests.
- Exercise provisioning renewal and an in-place signed upgrade/reinstall without
  deleting the app; verify pairing and intended state under a compatible identity.
- Restore a Mac backup taken before device revocation and confirm the revoked
  credential remains rejected after restart and interrupted-restore recovery.
- Verify cache expiry offline and cache/credential removal when revocation is
  detected, independently from immediate server-side access revocation.

## 13. Performance and reliability targets

- Show useful startup status immediately.
- Reach an interactive window within 10 seconds on the target development Mac
  under ordinary conditions; continue showing a precise stage if a migration
  needs longer.
- Avoid duplicating existing scan data or caches during normal upgrades.
- Keep the UI responsive while scans and reports run in the sidecar.
- Bound log storage with rotation and retention.
- Never leave an orphaned sidecar after normal quit.
- Never start two sidecars against the same database from duplicate launches.
- Persist sufficient job state to explain an interrupted scan after relaunch.
- Enforce the bounded local shutdown and retry rules in Section 9. Test writes
  under concurrent job load; short SQLite transactions and bounded busy handling
  are required before considering any database-engine change.

## 14. Distribution, licensing, and privacy gates

The local personal Mac build can proceed before public-release work. Before the
application is offered to other users, complete all of the following:

- Obtain Massive's written confirmation or applicable partner terms for a
  commercial application in which each user supplies or authorizes their own
  Massive entitlement.
- Confirm whether Massive provides a supported third-party OAuth flow. If it
  does, replace manual API-key entry for public builds. Never collect Massive
  account passwords.
- Determine permitted caching, derived analytics, PDF export, AI-analysis, and
  display behavior for every licensed dataset.
- Complete legal review for investment-screening and AI-ranking language.
- Audit third-party software licenses and ship required notices.
- Publish privacy and retention policies before collecting data from other
  users.
- Enroll in the appropriate Apple Developer Program and establish signing,
  notarization, certificate protection, and release ownership.

These public-release gates do not defer local iPhone signing, Developer Mode, or
provisioning setup until Phase 7. Complete those under Section 6.2 before the
Phase 5 device proof, with explicit user approval for any paid enrollment.

## 15. Relationship to the AI Analysis plan

`AI_ANALYSIS_IMPLEMENTATION_PLAN.md` remains the source of truth for AI product
behavior. For the local Mac milestone, its implementation must use the path,
Keychain, lifecycle, diagnostics, and packaging services defined here.

The AI feature must not assume that a browser session owns the backend. Its
durable analysis history remains in local SQLite, and any OpenAI request in the
Mac application is made by the packaged backend. The later iPhone companion
will display and initiate those analyses through the paired Mac; it will not
store the OpenAI API key or call OpenAI directly.

The AI plan's description of the current in-memory `JobRegistry` is historical
implementation context. Phase 2 establishes a durable common job lifecycle
before Phase 2A; AI-specific tables remain the source of analysis content,
per-stock progress, and history. Use one versioned migration mechanism and one
consistent job lifecycle rather than parallel, conflicting restart behavior.
Preserve the AI plan's product scope and cost-aware retries. The small packaged
production workflow and security gates in Phase 2 must pass first.

If a future public release adopts a hosted multi-user backend, use the runbook
in Section 16 and add a provider-specific infrastructure checklist. That work
must cover accounts, server-held credentials, the selected hosted database,
durable cloud jobs, synchronized history, subscription entitlements, and deletion.
Do not silently reinterpret the local-first decisions in either plan.

## 16. Deferred hosted database setup and migration runbook

### 16.1 When a hosted database is appropriate

PostgreSQL is the recommended default if a hosted, multi-user backend is
separately approved. It is an architectural choice, not a technical requirement
for every deployment. The hosted-backend decision would support one or more of
the following:

- using the iPhone application when the Mac is unavailable or on another
  network;
- synchronizing accounts, watchlists, reports, scans, and AI history across
  devices;
- running scans and AI jobs after every client application has closed; or
- distributing the product publicly as a managed service.

Neither PostgreSQL nor MariaDB is needed for the local Mac desktop application
or the first same-network iPhone companion. Do not install a database server,
create a hosted database, migrate data to a service, or incur hosting costs before
the cloud-backend decision is approved. SQLite remains the local store even if a
later hosted service uses a different engine; synchronized record authority is
defined separately in Section 16.8.

Database selection rationale:

| Consideration | PostgreSQL default | MariaDB alternative |
| --- | --- | --- |
| Relational application records | Suitable for accounts, watchlists, job metadata, and report references | Also suitable for these records |
| Analysis documents | `jsonb` supports document queries and specialized indexing | JSON is validated text; selected fields can use indexed generated columns |
| Tenant isolation | Built-in row-security policies can add database enforcement | Restricted views/privileges can supplement application authorization |
| Reason to choose | Fits the proposed document queries and hosted tenant model without an existing engine constraint | Existing operational expertise, infrastructure, or demonstrated hosting/workload advantage |

This is a fit-based recommendation, not a benchmark claim. Both engines require
application authorization, tenant tests, backups, and operational ownership.
PostgreSQL row security must use properly configured non-owner runtime roles
without bypass privileges; it does not replace API authorization. MariaDB's
isolation design must be reviewed and tested if selected. Keep frequently queried
business fields typed and relational rather than placing everything in JSON.

The relevant capabilities are documented in
[PostgreSQL JSON support](https://www.postgresql.org/docs/current/datatype-json.html),
[PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html),
[MariaDB JSON storage](https://mariadb.com/docs/server/reference/data-types/string-data-types/json),
[MariaDB generated-column indexing](https://mariadb.com/docs/server/ha-and-performance/optimization-and-tuning/query-optimizations/virtual-column-support-in-the-optimizer),
and [MariaDB access-control views](https://mariadb.com/docs/server/mariadb-quickstart-guides/mariadb-views-guide).

The following runbook uses PostgreSQL as the default implementation. If MariaDB
is selected, record the decision and adapt the driver, migrations, JSON/index
design, permissions, and provider runbook before provisioning; do not maintain
both hosted engines without an actual requirement.

### 16.2 Decisions required before creating the database

Finalize these items at the beginning of the hosted-backend phase:

1. Confirm the database-engine decision and select the cloud application host
   and managed provider. Re-evaluate PostgreSQL versus MariaDB against current
   expertise, provider capabilities/costs, and representative workloads.
2. Choose a region near the expected users and in the same region as the API
   and worker services.
3. Estimate development, staging, and production storage, connections, worker
   concurrency, backup retention, and monthly budget.
4. Define which data synchronizes to the service and which device-local data
   remains private.
5. Define account ownership, authentication, deletion, export, and retention
   behavior.
6. Decide whether existing personal Mac data will remain local, be imported
   once, or participate in ongoing synchronization. Complete the record-authority,
   conflict, deletion, and offline-retry contract in Section 16.8 before building
   synchronization or planning production cutover.
7. Complete the Massive, legal, and privacy gates before uploading licensed
   market data or inviting public users.

The selected provider will receive a separate provider-specific setup checklist
with exact console fields. This runbook intentionally avoids steps that could
become incorrect if a different provider is selected.

### 16.3 User-owned infrastructure steps

When the hosted phase is approved, the product owner will:

1. Create the cloud-provider organization under a product-owned email address,
   not a developer's personal account.
2. Enable multi-factor authentication, save recovery information securely, and
   add a second trusted administrator if appropriate.
3. Configure billing, a monthly budget, and usage alerts before provisioning
   resources.
4. Create separate development, staging, and production projects. Production
   data must never be used casually for development or automated tests.
5. Select the approved region and provision managed PostgreSQL using a currently
   supported version.
6. Enable encryption in transit, encryption at rest, automated backups, and
   point-in-time recovery where the provider supports it.
7. Configure the maintenance window, backup retention, storage-growth alerts,
   connection alerts, and database health notifications.
8. Create or approve a product domain and DNS records for the hosted API.
9. Grant deployment automation and maintainers only the minimum roles they need.
   Do not share an all-powerful provider login.
10. Place connection credentials in the hosting provider's secret manager or
    protected environment settings. Never commit them, place them in the app,
    paste them into a plan, or send them through ordinary chat.
11. Approve the staging cutover after reviewing reconciliation and restore-test
    evidence.
12. Approve the production cutover and the documented rollback window.

The user does not need to create tables, write SQL, run schema migrations, or
manually copy SQLite data. Those are application implementation tasks.

### 16.4 Application implementation steps

The application work will:

1. Inventory all current SQLite databases and classify each table as canonical
   user data, job state, provider cache, rebuildable cache, or secret data.
2. Define a multi-user relational model. Canonical records will include stable
   identifiers, `user_id` ownership, timestamps, constraints, and deletion
   behavior.
3. Keep PDFs and large immutable report artifacts in encrypted object storage;
   PostgreSQL will store their metadata and storage identifiers rather than
   large filesystem blobs.
4. Extend the repository interfaces established in Phases 1 and 2 with hosted
   implementations. Keep local and hosted data modes explicit. Clients connect
   through the authenticated hosted API; never embed hosted database credentials
   or make a Mac/iPhone client connect directly to the production database.
5. Implement hosted SQLAlchemy 2 models and repositories with portability tests
   for shared record semantics; retain the local SQLite implementation. Use
   synchronous database access through appropriate request/worker execution so
   it does not block an async event loop; adopt async access if measurements
   justify it. Test IDs, timestamps, numeric precision, and JSON serialization
   across local export and hosted import.
6. Add Alembic migrations as the only supported way to modify the hosted schema.
   Application startup must not create or alter production tables ad hoc.
7. Add a PostgreSQL driver, bounded connection pooling, transaction boundaries,
   retry rules for transient failures, and database health checks.
8. Add tenant-isolation tests proving one account cannot read, update, export,
   or delete another account's records.
9. Extend the durable local job contract from Phase 2 with a hosted durable queue,
   worker ownership/leases, progress, cancellation, recovery, and results. A job
   has one execution authority; local and cloud workers must not both execute a
   synchronized copy of the same job.
10. Move server-held provider credentials into a managed secret system with
    per-user encryption where bring-your-own credentials are approved.
11. Implement account data export and deletion, including associated reports,
    AI history, credentials, and queued work.
12. Build a versioned SQLite export/import tool with dry-run mode, validation,
    repeat-safe identifiers, and a manifest of record counts and checksums.
13. Add the indexes and query limits required by measured staging workloads.
14. Add metrics for connection usage, slow queries, errors, storage growth,
    queue delay, and migration status without logging sensitive values.
15. If ongoing synchronization is selected, implement the authority, revision,
    conflict, tombstone, outbox, and idempotency rules in Section 16.8 and test
    them independently of one-time database migration.

### 16.5 Environment creation order

Create and validate the hosted environments in this order:

1. **Local integration:** Run an expendable PostgreSQL instance for automated
   compatibility and migration tests. It contains generated test data only.
2. **Hosted development:** Verify deployment, secrets, migrations, job workers,
   and database connectivity without personal production data.
3. **Hosted staging:** Exercise realistic volumes, account isolation, SQLite
   import, backup restoration, failure recovery, and application upgrades.
4. **Hosted production:** Provision only after staging acceptance, legal and
   licensing approval, operational ownership, and a tested rollback procedure.

Never point local automated tests at staging or production. Never use a
production connection string as a development default.

### 16.6 Migration and cutover procedure

For each environment:

1. Provision the empty database and application roles.
2. Run migrations using a dedicated migration role.
3. Start the API with its restricted runtime role.
4. Run health, authorization, transaction, and job-queue smoke tests.
5. Import a sanitized SQLite fixture and reconcile every table's counts,
   identifiers, ownership, totals, and report references.
6. Run representative scanner, fundamentals, watchlist, journal, report, and AI
   workflows.
7. Take a managed backup and restore it into a separate verification database.
8. Measure queries, indexes, pool saturation, worker concurrency, and storage.
9. Record the deployed application version and Alembic revision.

For production cutover:

1. Announce a maintenance window if existing data will be uploaded.
2. Stop mutations in the source being migrated while retaining read access.
3. Create an immutable source backup and migration manifest.
4. Run the repeat-safe import and reconciliation report.
5. Complete an owner-approved smoke test using non-destructive operations.
6. Enable production traffic gradually and monitor errors and resource usage.
7. Retain the source backup and the previous application version for the agreed
   rollback period.
8. Roll back if reconciliation, tenant isolation, or critical workflows fail.

### 16.7 Hosted database acceptance criteria

The hosted database setup is complete only when:

- development, staging, and production have separate databases, secrets, and
  access controls;
- all schema changes are versioned, reviewed, repeatable migrations;
- TLS is required and production is not unnecessarily open to the public
  internet;
- runtime roles cannot perform administrative schema operations;
- account isolation has automated positive and negative tests;
- backups are enabled and an actual restore has succeeded;
- SQLite migration produces an auditable reconciliation report;
- deployed services survive database restart and transient-connection tests;
- monitoring and budget alerts reach an accountable owner;
- credentials are absent from Git, client bundles, logs, and diagnostics;
- the rollback procedure has been exercised in staging; and
- if synchronization is enabled, the separate Section 16.8 acceptance checks
  pass. A successful import does not satisfy synchronization acceptance.

### 16.8 Data authority and optional synchronization

This section is a Phase 7 design/acceptance gate, not authorization to add cloud
storage or synchronization during the local Mac/iPhone phases.

Before implementation, record each entity's authority and synchronization scope:

| Record class | Local Mac and LAN companion | If hosted synchronization is approved |
| --- | --- | --- |
| User business records | Mac SQLite is authoritative; the phone uses the Mac API | Hosted service is authoritative for explicitly opted-in records; SQLite holds local replicas and pending edits |
| Private, unsynchronized records | Mac SQLite is authoritative | Remain local; do not upload implicitly |
| Scan/AI jobs | Mac backend owns execution and durable job state | Each job is assigned to one Mac or hosted executor; synchronizing status does not schedule another execution |
| Saved reports/analysis artifacts | Durable local files with database references | Immutable uploaded objects with stable IDs/digests and tenant-scoped metadata |
| Rebuildable provider caches | Local caches subject to retention/licensing | Excluded by default; any sharing requires a separate data-permission decision |
| Provider/device credentials | Platform Keychain or protected server-side verifier | Never ordinary synchronized records; use separately authorized credential provisioning |
| UI preferences | Device-local, versioned storage | Remain device-local unless a specific setting is deliberately made portable |

Required behavior:

- Use stable IDs independent of database row numbers, tenant ownership, schema
  versions, and server-issued record revisions. Preserve an import ID mapping
  and do not treat local timestamps as proof that an edit is newest.
- Send edits with their expected base revision. The service applies accepted
  edits atomically; stale edits produce an explicit conflict retaining both
  versions for resolution. Define entity-specific merge rules; do not silently
  overwrite conflicting trades, watchlists, or analysis revisions.
- Keep pending offline mutations in a durable outbox with idempotency keys and
  acknowledgements. Retried uploads must not duplicate records, jobs, or reports.
  Show pending/conflicted status separately from synchronized data.
- Use deletion tombstones and a documented retention/resynchronization policy
  so a disconnected replica cannot resurrect a deleted record. Account deletion
  must cover hosted records, objects, queued jobs, and subsequent device cleanup.
- Keep immutable analysis/report versions immutable; modifications create a
  new linked revision. Preserve source snapshot digests during serialization.
- Define account switching, sign-out, revoked-device handling, cache isolation,
  expired synchronization cursors, and explicit local-to-hosted opt-in. Do not
  switch data modes or merge accounts merely because an endpoint becomes reachable.
- Bound retries and reconcile uncertain responses. Initial migration must
  establish a consistent synchronization checkpoint; rollback must account for
  acknowledged writes made after cutover rather than discarding them silently.

Acceptance must demonstrate concurrent edits from two clients, prolonged offline
edits, duplicate delivery, interruption before/after acknowledgement, deletion
while a client is offline, expired cursors, account isolation, and recovery after
server restart. One-time import and ongoing synchronization are separate results.

## 17. Definition of done

### Mac application

The Mac milestone is complete when a user can install and launch Swing Scanner
from Finder, perform the full existing workflow without Terminal or an external
browser, migrate browser-held business records safely, restore a validated
backup, preserve data and UI state across upgrades, use credentials stored in
Keychain, recover interrupted jobs with visible diagnostics, and quit without
leaving backend processes running. Competing processes must not access an owned
data root during normal use or recovery. The full packaged acceptance and
advertised macOS/architecture matrix must pass; distribution claims additionally
require the actual Phase 4 production-signing evidence.

### iPhone companion

The iPhone milestone is complete when a locally installed application can pair
securely with an explicitly enabled Mac, provide the approved mobile feature
set with purpose-built layouts, retain appropriate state, control and monitor
Mac-executed scans, and lose server access immediately after revocation. Cached
data follows the bounded offline/purge policy in Section 8; temporary transport
loss retains pairing, while backup restoration cannot revive old authorizations.
Physical-device trust, permission, and the user-confirmed hardware/OS matrix must
pass. Local provisioning, renewal, and in-place upgrade/reinstall behavior must
be documented and verified before declaring the companion milestone complete.

### Public release

Public release is not included in either initial milestone. It is complete only
after market-data permission, legal review, privacy obligations, Apple signing
and review requirements, and any cloud or subscription architecture have been
separately approved and implemented.

## 18. Audit improvement coverage

First audit accepted on 2026-09-06; the six second-audit corrections were accepted
on 2026-09-07, followed by three third-audit refinements on the same date. Each
recommendation is represented below; implementation remains pending in its
assigned phase except the completed Phase 0 proof. These tables are traceability
checklists, not claims that later gates pass. The minimum iOS version remains a
separate pending user decision under Section 2.1.

| Audit improvement | Requirement location | Delivery/acceptance owner |
| --- | --- | --- |
| Preserve browser-held business data, including Planned Trades | Section 7.1 | Phase 1 export/import and reconciliation |
| Specify consistent backups, credential recovery, restore, and rollback | Section 7.2 | Phase 1 before path changes/import; Phase 4 upgrades |
| Persist local jobs and define safe shutdown/retry | Section 9 | Phase 2 before AI; Phase 2A extends it |
| Add CSP, native permissions, navigation, and untrusted-content controls | Section 8 | Phase 2 production security gates |
| Define Keychain ownership/delivery and legacy-secret boundaries | Section 8 | Phase 2 credential recovery and replacement checks |
| Validate packaged production work and signing layout earlier | Sections 6 and 11 | Phase 2 before Phase 2A; Phase 4 distribution |
| Prove mobile discovery, TLS trust, pairing, and revocation on real devices | Sections 8 and 11 | Phase 5 before mobile screens; Phase 6 full acceptance |
| Define cloud record authority, conflicts, deletes, and offline retries | Section 16.8 | Phase 7 only if hosted synchronization is approved |
| Correct the bundle/data diagram | Section 3.1 | Plan corrected; Phase 1 path checks |
| Use standard cache directories and safe cache deletion | Section 7 | Phase 1 |
| Establish API versions and platform adapters before mobile work | Section 6 | Phases 1 and 2; extended in Phase 5 |
| Define minimum OS/hardware and evidence for compatibility | Section 2.1 | macOS Tahoe 26+ and iPhone 15+; Phases 2, 4, 5, and 6 |
| Make Intel support an optional expansion | Section 2.1 | Separate product decision |
| Separate repeatable builds from identical signed bytes | Phase 4 | Release manifests, archived artifacts, and checksums |
| Treat PostgreSQL as a default choice and evaluate MariaDB fairly | Section 16.1 | No local engine change; decision at hosted approval |

### Second-audit corrections

| Finding | Requirement location | Delivery/acceptance owner |
| --- | --- | --- |
| R2-1: Enforce data ownership before migration, not only in Phase 2 | Sections 7.2 and 7.3 | Phase 1 ownership and concurrent launch/import/restore tests; Phase 2 adds window focusing |
| R2-2: Prevent backup restoration from undoing phone revocation | Sections 7.2 and 8 | Phase 1 restore boundary; Phase 5 invalidation and restore-after-revocation tests; Phase 6 full acceptance |
| R2-3: Separate temporary loss, explicit unpairing, and revocation | Sections 8 and 10 | Phase 5 connection proof; Phase 6 cache/reconnect and online/offline unpairing acceptance |
| R2-4: Separate local signing evidence from production hardening | Section 6.1 | Phase 2 mandatory local-integrity profile and explicit hardening status; Phase 4 actual distribution-profile acceptance |
| R2-5: Establish local iPhone provisioning before device testing | Section 6.2 | Phase 5 account/team/device setup; Phase 6 renewal and in-place upgrade/reinstall acceptance |
| R2-6: Confirm minimum iOS and make the test matrix executable | Section 2.1 | User confirms minimum iOS before Phase 5 target finalization; Phases 4–6 record actual hardware/OS evidence and resolve gaps |

### Third-audit refinements

| Finding | Requirement location | Delivery/acceptance owner |
| --- | --- | --- |
| R3-1: Preserve socket ownership during backend startup | Sections 3.1 and 8 | Phase 2 inherited-socket handoff, competing-bind/readiness/restart and cleanup tests |
| R3-2: Make ordinary watchlist retries and conflicting edits safe | Section 6.3 | Phase 2 API contract; Phase 5 enforcement across writers before mobile editing; Phase 6 mobile UX acceptance |
| R3-3: Permit explicitly selected read-only repository migration | Sections 7 and 7.1 | Phase 1 source-preservation, missing-source/key, and post-import independence tests |
