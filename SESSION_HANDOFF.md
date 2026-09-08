# Swing Scanner Session Handoff

- Last updated: 2026-09-07
- Working directory: `/Users/joe.rennick/scanner`
- Branch: `main`
- Pre-publication HEAD: `f9e2a88 Document deferred PostgreSQL setup`
- Publication scope: the user requested committing and pushing the completed
  Phase 0 proof, audited plan, and handoff on 2026-09-07. Exclude `.idea/` and
  generated build/resource output. Use `git status` and `git log` for the current
  commit and remote state; the working-tree inventory below predates publication.
- Codex CLI: `0.153.4`

## Start here in the next session

**Phase 0 — Mac packaging proof of concept is complete**, with every exit
criterion verified on 2026-09-06. The next implementation phase is **Phase 1 —
Filesystem and configuration readiness**. Phase 1 has not started.

The user accepted the first architecture audit's improvements on 2026-09-06,
then requested a second independent audit and approved all six plan corrections
on 2026-09-07. A third audit found three additional refinements, also approved
for the plan on 2026-09-07. Only the Apple plan and this handoff changed in these
documentation updates; Phase 1 and later work remain unimplemented. Section 18
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

1. Read the completed Phase 0 evidence and Phase 1 requirements.
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

- `APPLE_APPLICATION_IMPLEMENTATION_PLAN.md` — source of truth for Mac/iPhone
  architecture, phase order, PostgreSQL timing, testing, and release gates.
- `docs/PHASE_0_VERIFICATION.md` — completed native packaging acceptance
  evidence, isolation procedure, and known verification limits.
- `AI_ANALYSIS_IMPLEMENTATION_PLAN.md` — source of truth for the future AI
  watchlist-analysis workflow, follow-up refinement, history, and AI-created
  watchlists.
- `README.md` — existing browser development and project information.
