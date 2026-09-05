# Apple Application Implementation Plan

- Finalized: 2026-09-04
- Repository: `/Users/joe.rennick/scanner`
- Status: Approved plan; implementation has not started
- Delivery order: Local Mac desktop application first, trimmed-down iPhone
  companion second

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
| Initial Mac architecture | Support Apple Silicon first. Add an Intel/universal build before distributing to other Mac users. |
| Initial distribution | Install development builds locally, then produce a directly downloadable signed and notarized application and DMG. The Mac App Store is not required. |
| iPhone role | Treat iPhone as a companion, not a complete copy of the desktop product. |
| iPhone backend | Initially connect to an explicitly enabled Mac companion service on the same trusted network. Do not attempt to run the Python scanner on iOS. |
| Shared code | Share domain types, API client code, state schemas, charts, summaries, and appropriate React components. Use platform-specific navigation and layouts. |
| Public release | Defer App Store, multi-user cloud, subscriptions, and commercial distribution until their dedicated release gates are satisfied. |

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
└── local application resources
    ├── SQLite databases and caches
    ├── generated reports and exports
    └── logs
```

The Tauri host is the parent process. At launch it will select a private
loopback port, generate a random session secret, start the backend with those
values, wait for an authenticated readiness response, and only then present the
main interface. On quit it will request a graceful backend shutdown and ensure
the child process has exited.

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
- Secure pairing, connection status, and disconnect controls.

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
│   ├── python-sidecar.spec      reproducible Python sidecar definition
│   ├── entitlements/            signing entitlements
│   └── scripts/                 build and verification helpers
└── tests/
    └── packaging/               installed-application smoke tests
```

Use the existing frontend for both browser and Tauri builds. Introduce a small
runtime adapter instead of calling Tauri APIs directly throughout the React
component tree. Browser tests must remain able to substitute the adapter.

The Python sidecar will initially use a PyInstaller one-directory build rather
than a one-file executable. This reduces startup delay and makes native Python
dependencies easier to diagnose. The packaged sidecar must contain Python,
FastAPI, Uvicorn, report fonts/assets, certificate roots, and all imported
native libraries. Nuitka is the documented fallback only if a required native
dependency cannot be packaged reliably with PyInstaller.

## 7. Application data and migration

Packaged execution must not read or write mutable data inside the application
bundle or Git repository.

Use standard macOS locations:

```text
~/Library/Application Support/Swing Scanner/
├── data/             SQLite databases
├── cache/            market and SEC caches
├── reports/          generated report source files
├── exports/          temporary user exports
└── backups/          migration backups

~/Library/Logs/Swing Scanner/
└── scanner.log
```

Implementation requirements:

- Centralize all paths behind one application-path service.
- Support explicit data, cache, report, and log path overrides in development
  and tests.
- Remove assumptions that the current working directory is the repository.
- Give every persisted schema an explicit version and forward migration.
- Preserve browser `localStorage` behavior initially, but add a namespaced UI
  state version so future upgrades can migrate or discard individual fields
  safely.
- Provide an optional first-run import from the existing local scanner data.
- Preview what will be imported and create a backup before changing the new
  application database.
- Never silently delete the original development data after import.
- Exclude caches and temporary exports from essential-data backups.

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

### Sidecar API

- Bind to `127.0.0.1` only in normal desktop mode.
- Select the port at launch instead of assuming ports 8000 or 5173 are free.
- Generate a cryptographically random bearer secret on every application
  launch and pass it to the backend through the child-process environment.
- Require the secret for all application data and mutation endpoints.
- Pass the base URL and secret to the frontend in memory; do not persist the
  per-launch secret.
- Use an allowlist for browser-development origins and do not use unrestricted
  production CORS.
- Add request-size limits and retain existing input validation.
- Redact authorization headers, keys, and sensitive query parameters from logs.

### Mobile companion mode

Mobile access must be off by default. Enabling it will require an explicit Mac
setting and a pairing ceremony. Pairing will issue a revocable, device-specific
credential. The design must use encrypted transport, show connected devices,
allow immediate revocation, and never reuse the desktop sidecar session secret.

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
- Handle a second launch by focusing the existing window instead of starting a
  second backend against the same database.

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
- Make connection loss visible and retain the last successfully loaded data as
  read-only cached content where safe.
- Do not represent a stale cached result as current; always show its timestamp.

## 11. Delivery phases

### Phase 0 — Packaging proof of concept

- Install and configure Tauri 2 in `ui`.
- Open the existing production React build in a native Mac window.
- Build a minimal Python sidecar containing the FastAPI health endpoint.
- Start and stop the sidecar from Tauri.
- Demonstrate an authenticated frontend health request on an automatically
  selected loopback port.
- Package and launch the proof on the target Apple Silicon Mac.

Exit criteria:

- `Swing Scanner.app` opens without Terminal or an external browser.
- One application process owns one backend child process.
- Quit leaves no orphaned backend process.
- No fixed development port is required.

### Phase 1 — Filesystem and configuration readiness

- Add the centralized application-path service.
- Route every database, cache, report, export, and log path through it.
- Remove working-directory and repository-relative runtime assumptions.
- Add migrations and development-path overrides.
- Remove personal developer information from production defaults, including the
  current hard-coded SEC contact identity; collect or configure an appropriate
  application identity during setup.
- Implement first-run existing-data import and backup.

Exit criteria:

- The packaged application runs from `/Applications` with the repository
  unavailable.
- All mutable files appear only in the expected user directories.
- Existing data can be imported without modifying its source.

### Phase 2 — Secure desktop integration

- Implement Keychain credential storage and legacy-secret migration.
- Add per-launch local API authentication and production CORS rules.
- Add single-instance behavior.
- Implement readiness, graceful shutdown, crash detection, and bounded restart.
- Add rotating logs, redaction, and diagnostics export.

Exit criteria:

- Unauthorized local requests cannot read scanner data.
- Provider secrets do not appear in SQLite, frontend storage, or logs after
  migration.
- Backend failures produce a visible recovery screen.

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
- Add deterministic release build scripts and version stamping.
- Sign and notarize the application before sharing it with other Macs.
- Create a DMG with installation instructions.
- Add update-check capability only after a trusted release host and signing
  process exist; updates remain user-approved.
- Test clean install, upgrade, rollback from backup, and uninstall guidance.

Exit criteria:

- The application passes Gatekeeper on a clean supported Mac.
- Upgrade preserves user data and credentials.
- The release artifact and checksums are reproducible and archived.

### Phase 5 — Shared mobile foundation

- Define the stable API contract used by both platforms.
- Add runtime capability and responsive layout layers.
- Extract reusable ticker detail, chart, fundamentals, watchlist, report, and AI
  components without regressing desktop behavior.
- Add the Mac mobile-companion setting and design the secure pairing protocol.
- Create iPhone wireframes and a route-by-route capability matrix.

Exit criteria:

- Shared components have browser tests.
- Desktop behavior remains unchanged.
- The mobile scope is represented explicitly in navigation and capabilities.

### Phase 6 — Locally installed iPhone companion

- Create the Tauri iOS target.
- Implement mobile navigation and layouts.
- Add iOS local-network disclosure and permission handling.
- Implement pairing, connection recovery, credential storage in iOS Keychain,
  and device revocation from the Mac.
- Implement the included mobile feature set and read-only cached states.
- Run first in the iOS Simulator, then install directly on a registered iPhone
  through Xcode.

Exit criteria:

- The iPhone can pair with the Mac without exposing the desktop API publicly.
- Selected-ticker navigation remains consistent across mobile screens.
- A scan can be started and monitored while the Mac performs the work.
- Disconnecting or revoking the phone prevents subsequent access.

### Phase 7 — Optional public distribution architecture

This phase requires a separate approval before implementation:

- Decide whether to retain Mac-hosted companion access or deploy a cloud
  backend for access away from home.
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
- Add local API authentication and secret-redaction tests.
- Add sidecar command, startup timeout, crash, restart, and shutdown tests.
- Add packaged-resource checks for certificates, fonts, templates, and native
  Python libraries.
- Add platform-adapter tests with browser and Tauri implementations.
- Add mobile capability and state-restoration tests before the iOS build.

### Mac acceptance matrix

- First launch with no prior data.
- Import from the current development installation.
- Launch with ports 5173 and 8000 already occupied.
- Launch, minimize, restore, close window, and full quit.
- Relaunch after a forced backend termination.
- Run each scanner strategy, including a long fundamentals scan.
- Sort, filter, resize, auto-fit, hide, and restore result columns.
- Traverse candidates in the maximized chart.
- Navigate selected tickers among Scanner, Candidates, Fundamentals, and
  Watchlists.
- Create, export, open, and reveal every PDF report type.
- Configure, replace, test, and remove provider credentials.
- Upgrade over an older application version without losing user data.
- Run with the network unavailable and recover after connectivity returns.

### iPhone acceptance matrix

- First pairing, reconnection, revocation, and re-pairing.
- Mac unavailable, Mac sleeping, network changed, and permission denied states.
- Touch chart pan and zoom on supported frequencies.
- Selected ticker and filter state across navigation and relaunch.
- Start and monitor scanner progress.
- Review fundamentals, watchlists, reports, and AI history.
- Validate readable layouts with Dynamic Type and common phone sizes.

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

## 15. Relationship to the AI Analysis plan

`AI_ANALYSIS_IMPLEMENTATION_PLAN.md` remains the source of truth for AI product
behavior. For the local Mac milestone, its implementation must use the path,
Keychain, lifecycle, diagnostics, and packaging services defined here.

The AI feature must not assume that a browser session owns the backend. Its
durable analysis history remains in local SQLite, and any OpenAI request in the
Mac application is made by the packaged backend. The later iPhone companion
will display and initiate those analyses through the paired Mac; it will not
store the OpenAI API key or call OpenAI directly.

If a future public release adopts a hosted multi-user backend, create a separate
migration plan for accounts, server-held credentials, PostgreSQL, durable cloud
jobs, synchronized history, subscription entitlements, and deletion. Do not
silently reinterpret the local-first decisions in either plan.

## 16. Definition of done

### Mac application

The Mac milestone is complete when a user can install and launch Swing Scanner
from Finder, perform the full existing workflow without Terminal or an external
browser, preserve data and UI state across upgrades, use credentials stored in
Keychain, recover from a backend failure with visible diagnostics, and quit
without leaving backend processes running.

### iPhone companion

The iPhone milestone is complete when a locally installed application can pair
securely with an explicitly enabled Mac, provide the approved mobile feature
set with purpose-built layouts, retain appropriate state, control and monitor
Mac-executed scans, and lose access immediately after revocation.

### Public release

Public release is not included in either initial milestone. It is complete only
after market-data permission, legal review, privacy obligations, Apple signing
and review requirements, and any cloud or subscription architecture have been
separately approved and implemented.
