# AI Analysis Implementation Plan

- Finalized: 2026-09-04
- Repository: `/Users/joe.rennick/scanner`
- Status: Approved for implementation

This document supersedes the open-decision sections in
`docs/04-ai-analysis-handoff.md`. It defines the implementation-ready plan for
an OpenAI-powered watchlist analysis workflow, durable analysis history,
follow-up conversations, recommendation revisions, AI-derived watchlists, and
PDF reporting.

## 1. Product outcome

Add an **AI Analysis** feature that lets a user analyze selected stocks or an
entire saved watchlist for high-potential growth opportunities. The scanner
will combine an immutable snapshot of its own data, the existing exported
watchlist PDF, and optional current web research. It will rank every analyzed
stock, preserve the findings locally, support follow-up questions, and create a
new refined watchlist from the latest recommendation only after user approval.

This is an OpenAI API integration. It does not automate ChatGPT Web, share
ChatGPT sessions, or request ChatGPT credentials.

## 2. Finalized product decisions

| Area | Final decision |
| --- | --- |
| API | Use the OpenAI Responses API, not ChatGPT Web automation. |
| Model | `gpt-5.6-terra`. |
| Reasoning | `medium` for the entire run and its follow-ups. Do not change it in the middle of a run. |
| Credential | Store the API key in macOS Keychain. Support `OPENAI_API_KEY` as a development/server fallback. |
| Analysis selection | If rows are selected, analyze those rows. Otherwise analyze the entire active watchlist. |
| Preferred size | 10 stocks. Warn and require confirmation above 20. Enforce a version-1 hard cap of 50. |
| Orchestration | Group work into chunks of 10, with at most 3 concurrent per-stock requests. Persist every stock result immediately. |
| API processing | Use normal interactive Responses calls. Do not use the asynchronous Batch API in version 1. |
| Web research | User-selectable and enabled by default. Save citations and an information-current-as-of timestamp. |
| Ranking | Analyze stocks independently, then run one final synthesis across all validated stock results. |
| Refined-list default | Select up to 10 `Include` stocks with medium or high confidence. High risk alone does not automatically exclude a stock. |
| Data mutation | The model may propose actions, but only the scanner validates and executes them after a visible confirmation. |
| Follow-ups | Include one persistent follow-up conversation per analysis in version 1. |
| Recommendation changes | Store the initial recommendation as Version 1 and create a new revision whenever a follow-up materially changes inclusion, classification, or rank. |
| Watchlist creation | Always use the latest recommendation revision, show a complete preview, and require approval. Never modify the source watchlist. |
| AI provenance | Permanently identify AI-derived watchlists with an `AI Recommended` badge, origin metadata, and a link to the exact analysis revision. |
| Local history | SQLite is the canonical record for analysis history and visible conversations; do not depend on indefinite OpenAI retention. |

## 3. Scope

### Included in version 1

- Connect, verify, replace, test, and disconnect an OpenAI API credential.
- Start analysis from a saved watchlist for selected rows or the full list.
- Submit the exported watchlist PDF and structured scanner data.
- Analyze up to 50 stocks with durable per-stock progress.
- Use current web research by default and display source citations.
- Produce a structured ranking and detailed per-stock findings.
- Preserve complete, partial, cancelled, interrupted, and failed runs.
- Browse historical analyses on a dedicated page.
- Ask persistent follow-up questions about a completed analysis.
- Track recommendation changes as immutable revisions.
- Create a reviewed, AI-derived saved watchlist from the latest revision.
- Export an analysis PDF and identify AI provenance in watchlist PDFs.
- Restore relevant UI state after refresh and navigation.

### Explicitly excluded from version 1

- Logging in with a ChatGPT email, password, cookie, or browser session.
- Automatically operating `chatgpt.com`.
- Placing trades or connecting AI directly to a brokerage.
- Allowing AI to delete or overwrite watchlists, journal records, reports, or
  settings.
- Allowing AI to execute arbitrary application or operating-system commands.
- Adding stocks that were not part of the analyzed snapshot.
- Automatically creating a watchlist without user confirmation.
- Running scheduled or overnight Batch API analyses.
- Sharing analyses between application users or devices.

## 4. User experience

### 4.1 Connect OpenAI

The Settings page and AI Analysis preflight page will provide a **Connect
OpenAI API** card with:

- a masked API-key field;
- a link to the OpenAI API-key management page;
- **Save and Verify**, **Test Connection**, **Replace Key**, and **Disconnect**;
- connection source, last verification time, and masked key suffix;
- an explanation that API usage is billed separately from ChatGPT; and
- a summary of which scanner data is sent to OpenAI.

On save, the backend must verify the new key before replacing an existing valid
key. The browser must clear the plaintext field immediately after submission.
No response may return the saved key.

Credential resolution order is:

1. `OPENAI_API_KEY`, when set for development or server operation;
2. the macOS Keychain entry used by the scanner; and
3. unconfigured.

When the environment variable is active, the UI displays **Configured by
environment** and does not claim that Disconnect can remove it.

### 4.2 Start an analysis

Add **Analyze with AI** to the Watchlists page.

- When one or more rows are selected, label it **Analyze N Selected Stocks**.
- When no rows are selected, label it **Analyze Entire Watchlist (N)**.
- Disable it for an empty list.
- Warn before analyzing more than 20 stocks.
- Reject more than 50 stocks with an actionable message.

The preflight displays:

- source watchlist and stock count;
- selected tickers;
- model and reasoning level;
- whether current web research is enabled;
- the per-run web/tool limit;
- a reminder that the saved snapshot will not change if the source watchlist is
  later edited; and
- **Start Analysis** and **Cancel**.

The web-research switch defaults on and preserves its most recent user setting.
When off, results display **Scanner data only — no current web research**.

### 4.3 Progress and recovery

Navigate immediately to `/ai-analysis/<analysis-id>` after creating the durable
run. Use a progress display consistent with the scanner progress UI.

Stages include:

1. Preparing watchlist snapshot
2. Generating analysis package
3. Uploading source report
4. Analyzing `<ticker>` (`N` of `total`)
5. Building final ranking
6. Saving results
7. Complete

Show counts for completed, failed, skipped, and remaining stocks. Persist the
stage and counts in SQLite so refresh and navigation do not lose progress.

Cancellation stops scheduling new stock requests, lets already-active requests
finish safely, saves their results, and marks the run cancelled. A retry resumes
failed or unfinished stocks rather than charging again for completed work.

Because the existing `JobRegistry` is in memory, the durable analysis record is
the source of truth. At backend startup, any run left in `queued` or `running`
state is marked `interrupted` and offered for retry.

### 4.4 AI Analysis page

Add **AI Analysis** to primary navigation.

Routes:

- `/ai-analysis` — history and latest selected analysis;
- `/ai-analysis/new?watchlistId=<id>` — connection and run preflight;
- `/ai-analysis/<analysis-id>` — exact historical analysis;
- `/ai-analysis/<analysis-id>?revision=<n>` — exact recommendation revision.

The page contains:

- a history panel with watchlist, date, stock count, top stock, model, and
  status;
- an analysis header with source snapshot time, model, reasoning, research
  mode, revision, and progress;
- actions for Cancel, Retry, Re-analyze, Export PDF, and Create Refined
  Watchlist;
- a sortable ranking table;
- a selected-stock detail panel; and
- an **Ask about this analysis** conversation panel.

The ranking table includes:

- Rank
- Ticker
- Recommendation (`Include`, `Watch`, or `Exclude`)
- Overall score
- Growth score
- Valuation assessment
- Risk
- Confidence
- Short thesis

The stock detail includes growth evidence, valuation, business quality,
catalysts, risks, conflicting evidence, data limitations, scanner inputs,
citations, and data-as-of dates.

### 4.5 Follow-up conversation and recommendation revisions

Each analysis has one conversation scoped to its immutable snapshot and current
recommendation revision. A follow-up response must contain a structured
`recommendation_impact` in addition to its visible answer:

- `no_change`;
- `add` an analyzed ticker;
- `remove` an analyzed ticker;
- `rerank` one or more analyzed tickers; or
- `reclassify` a ticker among Include, Watch, and Exclude.

A material change creates an immutable new revision. The UI displays a concise
diff such as:

> Recommendation updated: AMD removed — Current Recommendation v2

A question that only explains an existing decision produces `no_change` and
does not create a revision. The original analysis and every prior revision
remain accessible.

If new web research is used in a follow-up, save its citations and display a new
information-current-as-of timestamp. A follow-up never silently edits a saved
watchlist.

### 4.6 Create a refined watchlist

**Create Refined Watchlist** always starts from the latest recommendation
revision, never silently from the initial ranking.

Default selection:

- include at most the first 10 stocks classified `Include`;
- require confidence of `medium` or `high`;
- do not exclude solely because risk is high;
- never introduce a ticker outside the analyzed snapshot; and
- create no proposal if nothing qualifies.

The review dialog shows:

- analysis and revision used;
- proposed watchlist name;
- selected stocks in their recommended order;
- excluded stocks and brief reasons;
- rank, score, confidence, and risk;
- checkboxes to add or remove analyzed stocks; and
- **Approve and Create** and **Cancel**.

Default name:

`<Source Watchlist> — AI Growth Picks — <YYYY-MM-DD>`

Applying a proposal is idempotent. Repeating a request after a network error
must not create duplicate watchlists.

### 4.7 AI provenance in watchlists

AI origin is stored as metadata, not inferred from a name.

- Display a sparkle icon and **AI Recommended** badge next to an AI-derived
  watchlist in selectors and the Watchlists page header.
- Display **AI Recommended · Modified** after the user manually adds or removes
  holdings. Renaming alone does not mark the membership as modified.
- Show a header banner with creation date, source watchlist, model, analysis
  revision, and **View Analysis** link.
- Preserve the original AI rank, score, confidence, and inclusion reason for
  each AI-selected item.
- Label subsequently added items **Manual**.
- Keep provenance after manual edits; do not imply that an old recommendation
  is still current.
- Include origin, analysis date, revision, and an AI-research disclosure in
  exported watchlist PDFs.

## 5. Data submitted for analysis

Create one immutable snapshot before making any OpenAI request. It contains:

- source watchlist ID and name;
- selected ticker list and ordering;
- saved-watchlist item data;
- latest matching scanner row;
- latest cached fundamentals, validation, quality, valuation, and risk data;
- market-data and fundamentals data-as-of timestamps;
- generated watchlist PDF path and digest; and
- snapshot schema version.

For a selected subset, generate an analysis PDF containing only the selected
stocks while retaining the source watchlist name and a visible **Selected
subset** label.

Upload the PDF once for the run. Submit the full PDF and compact structured
snapshot to the initial/final analysis context. Per-stock requests receive the
relevant structured stock record and shared methodology so the entire PDF is
not repeatedly processed. Delete the remote uploaded file on terminal run
cleanup when possible; keep the local PDF and snapshot as the durable record.

## 6. Prompt and structured contracts

Preserve the requested primary prompt exactly:

> I'm going to give you the full list (including what I already sent you).
> Analyze the stocks one by one on the list and then rate them in order with the
> best being at the top. I'm looking for high potential growth stocks.

Add versioned backend developer instructions requiring:

- consistent criteria across every stock;
- evaluation of growth, valuation, financial quality, catalysts, competitive
  position, and risk;
- separation of scanner-provided facts from web-researched facts;
- citations for web-derived claims;
- no invented values or unsupported certainty;
- `insufficient_evidence` when facts cannot support a conclusion;
- concise explanations for scores and classifications;
- a clear research-support, not investment-advice disclosure; and
- strict adherence to application-owned JSON schemas.

### 6.1 Per-stock result

Use strict structured output with at least:

- `ticker`
- `status`: `complete`, `insufficient_evidence`, or `failed`
- `recommendation`: `include`, `watch`, or `exclude`
- `overall_score`: 0–100
- `growth_score`: 0–100
- `valuation_assessment`
- `risk_level` and `risk_summary`
- `confidence`: `low`, `medium`, or `high`
- `thesis`
- `growth_evidence[]`
- `catalysts[]`
- `risks[]`
- `conflicting_evidence[]`
- `limitations[]`
- `scanner_facts_used[]`
- `sources[]` with title, URL, publisher, and date when available
- `information_current_as_of`

Reject malformed or out-of-domain results and retry validation at most once.
Do not silently coerce an unknown ticker or classification.

### 6.2 Final synthesis

The synthesis receives all validated per-stock results and produces:

- complete ordered ranking;
- consistent final classifications and scores;
- overall methodology summary;
- portfolio-level concentration or common-risk observations;
- excluded or failed tickers with reasons; and
- Recommendation Version 1.

The final synthesis does not repeat web research by default; it synthesizes the
cited per-stock results. This controls cost and reduces contradictory evidence.

### 6.3 Follow-up result

Every follow-up response contains:

- visible answer;
- citations used in that turn;
- `recommendation_impact` type;
- affected tickers and reasons;
- complete resulting ordered recommendation when a revision is proposed; and
- information-current-as-of timestamp.

The backend validates that all affected tickers belong to the immutable
analysis snapshot before accepting a revision.

## 7. Execution and cost controls

1. Validate credential and selection.
2. Create the SQLite analysis row and immutable snapshot before external work.
3. Generate the selected-list PDF and upload it once.
4. Partition stocks into ordered chunks of 10.
5. Run at most 3 per-stock OpenAI requests concurrently in a dedicated bounded
   executor or semaphore.
6. Use `gpt-5.6-terra` with `reasoning.effort=medium` for all stock requests.
7. When web research is enabled, allow up to 3 built-in web-search calls per
   stock request and save every returned source.
8. Persist each validated stock result and usage record immediately.
9. Continue after a per-stock failure and represent it explicitly.
10. Run final structured synthesis after all possible stock results finish.
11. Create Recommendation Version 1 and mark the run terminal.
12. Perform best-effort cleanup of the remote uploaded file.

Record token and tool usage when returned by the API. Display actual usage after
completion. Version 1 controls cost with the 50-stock cap, 3-request concurrency
cap, output-token limits, and web-tool-call limits rather than promising a
fixed dollar estimate that may become stale.

Do not retry rate limits, authentication failures, billing failures, or server
errors indefinitely. Use bounded exponential backoff for transient failures and
make costly retries visible to the user.

## 8. Persistence design

Use the existing SQLite database and idempotent schema initialization patterns.
Add explicit lightweight migrations for new columns; `CREATE TABLE IF NOT
EXISTS` alone is not enough for existing installations.

### 8.1 `ai_analysis_runs`

- identity and timestamps;
- source watchlist ID (nullable) and preserved source name;
- immutable snapshot JSON and schema version;
- local PDF path and digest;
- remote file ID while active;
- prompt and instruction version;
- requested and actual model;
- reasoning level and web-research setting;
- status, stage, progress counts, and cancellation flag;
- current recommendation revision number;
- visible summary and validated result JSON;
- OpenAI response and conversation IDs when available;
- token/tool usage totals; and
- structured error code, safe message, and retry metadata.

### 8.2 `ai_analysis_stock_results`

- analysis ID and ticker as a unique pair;
- request status and attempt count;
- rank, classifications, scores, risk, and confidence;
- thesis, evidence, catalysts, risks, and limitations JSON;
- sources JSON and information-current-as-of;
- scanner-input digest;
- OpenAI response ID and usage; and
- timestamps and safe error fields.

### 8.3 `ai_analysis_messages`

- message ID and analysis ID;
- role and visible content;
- citations JSON;
- recommendation-impact JSON;
- resulting revision number when applicable;
- OpenAI response ID; and
- timestamp.

### 8.4 `ai_analysis_revisions`

- analysis ID and monotonically increasing revision number;
- parent revision;
- trigger message ID, nullable for Version 1;
- complete ordered recommendation JSON;
- machine-readable diff JSON;
- summary and timestamp.

Revisions are immutable. The run points to the latest accepted analytical
revision. Creating a revision changes analysis state only; it does not mutate a
saved watchlist.

### 8.5 `ai_watchlist_proposals`

- proposal ID and idempotency key;
- source analysis and revision;
- proposed name and ordered items JSON;
- selection-rule JSON;
- status (`draft`, `applied`, or `cancelled`);
- created watchlist ID when applied; and
- timestamps.

### 8.6 Saved-watchlist lineage

Extend saved watchlists with optional:

- `origin_type`: `manual` or `ai_recommended`;
- source analysis ID and revision;
- source watchlist ID and preserved name;
- originating model and analysis timestamp;
- membership-modified timestamp; and
- creation proposal ID.

Store item-level AI rank, score, confidence, classification, inclusion reason,
and origin. Existing manual lists retain defaults and unchanged behavior.

## 9. Backend API surface

Exact Pydantic names may follow existing conventions, but the HTTP behavior is
fixed.

### Credential

- `GET /api/openai/credential`
- `PUT /api/openai/credential`
- `POST /api/openai/credential/test`
- `DELETE /api/openai/credential`

Status endpoints return metadata only. Credential request bodies and
authorization headers must be redacted from logs.

### Analyses

- `GET /api/ai/analyses`
- `POST /api/ai/watchlists/{watchlist_id}/analyses`
- `GET /api/ai/analyses/{analysis_id}`
- `POST /api/ai/analyses/{analysis_id}/cancel`
- `POST /api/ai/analyses/{analysis_id}/retry`
- `POST /api/ai/analyses/{analysis_id}/messages`
- `POST /api/ai/analyses/{analysis_id}/report`

The start body includes selected tickers or an explicit entire-list flag, web
research setting, and a client idempotency key. The response returns the durable
analysis ID immediately.

### Recommendation proposals

- `POST /api/ai/analyses/{analysis_id}/watchlist-proposals`
- `GET /api/ai/watchlist-proposals/{proposal_id}`
- `POST /api/ai/watchlist-proposals/{proposal_id}/apply`
- `POST /api/ai/watchlist-proposals/{proposal_id}/cancel`

Apply revalidates the exact analysis revision, tickers, duplicates, name, and
idempotency key inside one database transaction.

## 10. Backend implementation areas

Add the official OpenAI Python SDK and a macOS Keychain integration dependency
to `requirements.txt`. Hide both behind application-owned interfaces so tests
never require network access or real credentials.

New modules:

- `src/scanner/ai/openai_client.py` — Responses, files, web-tool options,
  redaction, and error translation;
- `src/scanner/ai/schemas.py` — strict provider-independent result contracts;
- `src/scanner/ai/prompts.py` — versioned prompt and developer instructions;
- `src/scanner/ai/watchlist_analysis.py` — durable orchestration;
- `src/scanner/ai/recommendations.py` — revision and proposal rules;
- `src/scanner/data/ai_analyses.py` — SQLite runs, results, messages, revisions,
  and proposals;
- `src/scanner/security/keychain.py` — OpenAI key storage interface and macOS
  implementation; and
- `src/scanner/reports/ai_analysis_report.py` — analysis PDF.

Extend:

- `src/scanner/api/app.py` with thin endpoints only;
- `src/scanner/api/schemas.py` with request/response models;
- `src/scanner/api/jobs.py` only where analysis job visibility requires it;
- `src/scanner/data/saved_watchlists.py` with lineage, item provenance, and
  transactional proposal application;
- `src/scanner/reports/saved_watchlist_report.py` with AI provenance; and
- `src/scanner/config/settings.py` with bounded AI defaults.

Do not put provider orchestration or persistence logic directly in
`src/scanner/api/app.py`.

## 11. Frontend implementation areas

New files:

- `ui/src/api/aiAnalyses.ts`
- `ui/src/features/ai-analysis/AIAnalysisPage.tsx`
- focused child components for history, progress, ranking, stock details,
  conversation, revision diff, credential connection, and proposal review.

Extend:

- `ui/src/routes.ts` and `ui/src/App.tsx` for AI Analysis navigation and dynamic
  routes;
- `ui/src/api/types.ts` with strict AI DTOs;
- `ui/src/api/queryKeys.ts` with list, detail, proposal, and credential keys;
- `ui/src/api/settings.ts` with credential operations;
- `ui/src/features/watchlists/WatchlistsPage.tsx` with Analyze, AI badges,
  lineage banner, View Analysis, and item provenance; and
- the Reports page to recognize AI analysis reports.

Page state key: `swing-scanner.ai-analysis.page.v1`.

Persist at least:

- history filters and selected analysis;
- selected revision and ticker;
- web-research preference;
- table sort and filters;
- panel widths or collapsed sections where applicable;
- conversation scroll position where practical; and
- an unsubmitted follow-up draft.

The analysis ID and revision also remain in the URL so browser navigation opens
the exact historical state. Sorting, filtering, refreshing, and navigating
between pages must not discard the active analysis or revision.

## 12. Reports

An AI Analysis PDF contains:

- source watchlist and immutable snapshot time;
- model, reasoning, research mode, analysis date, and revision;
- methodology and research-support disclosure;
- ordered ranking and classifications;
- detailed per-stock findings;
- citations and information-current-as-of dates;
- excluded, insufficient-evidence, and failed tickers; and
- recommendation-revision history or a concise link/reference to it.

Register the PDF with the existing Reports page and download endpoint. Repeated
generation for the same analysis revision should be deterministic where
practical and should not make another OpenAI call.

An AI-derived watchlist PDF includes its permanent AI provenance and indicates
whether membership has been manually modified.

## 13. Security, privacy, and failure handling

- Bind the local application to loopback as it does today.
- Never expose the OpenAI key to frontend storage, API responses, logs, reports,
  exceptions, or Git.
- Never store ChatGPT credentials.
- Mask credentials and clear plaintext UI state after submission.
- Use a dedicated OpenAI project/key so usage can be monitored separately.
- Explain that snapshot data, the PDF, and enabled web-search queries leave the
  local application.
- Keep the full local snapshot and results, but log only safe identifiers and
  summarized errors.
- Validate all model output before persistence or action.
- Require confirmation for every saved-watchlist write initiated from AI.
- Treat invalid key, access/entitlement, billing, rate limit, timeout, network,
  malformed output, file upload, and partial-stock errors distinctly.
- Preserve partial success and make retries explicit.
- Delete remote uploaded files on terminal cleanup where supported and report
  cleanup failure without failing an otherwise completed analysis.
- Do not expose deletion or trading tools to the model.

## 14. Test plan

### Backend unit and integration tests

- Keychain save, verify-before-replace, status, environment override, test, and
  disconnect without secret exposure.
- Log and exception redaction.
- Snapshot immutability after source watchlist edits or deletion.
- Selected-subset and entire-list behavior.
- 20-stock warning contract and 50-stock hard limit.
- Chunk size 10 and concurrency never above 3.
- PDF/structured request construction and remote-file cleanup.
- Web research enabled/disabled behavior and source persistence.
- Strict per-stock, synthesis, and follow-up schema validation.
- Immediate per-stock persistence and partial failure handling.
- Cancel, retry, rate-limit, and backend-restart interruption behavior.
- Final ranking from all successful stock results.
- Recommendation Version 1 and follow-up revision diffs.
- `no_change` follow-up does not create a revision.
- Revision cannot add an unanalyzed ticker.
- Proposal defaults use the latest revision, not the initial ranking.
- Proposal validation, transactionality, and idempotent application.
- Source watchlist is never mutated.
- AI lineage and manual-modification detection.
- Analysis and watchlist PDF metadata.

### Frontend tests

- First-use connection and automatic continuation after verification.
- Selected-row versus entire-list button labels.
- Preflight, warning, and cap states.
- Progress, partial results, cancellation, retry, and interrupted run display.
- Refresh and cross-page state restoration.
- History opens the exact analysis and revision.
- Ranking sorting/filtering preserves selection.
- Per-stock details and citations render safely.
- Follow-up draft and conversation persistence.
- Recommendation change card and version navigation.
- Create Watchlist preview uses the latest revision.
- User approval is required before creation.
- AI Recommended and AI Recommended · Modified badges.
- View Analysis returns to the originating revision.
- Manual items are labeled correctly.
- Reports-page and PDF download behavior.

### End-to-end acceptance scenario

1. Connect and verify an OpenAI API key, then restart frontend and backend.
2. Confirm the connection remains available without exposing the key.
3. Select 10 stocks from a saved watchlist and start analysis with web research.
4. Observe per-stock progress and refresh during the run.
5. Confirm completed results and citations survive the refresh.
6. Change or delete the source watchlist and reopen the immutable analysis.
7. Ask a follow-up that removes one recommended stock.
8. Confirm the UI creates Recommendation Version 2 and displays the diff.
9. Choose Create Refined Watchlist and confirm the removed stock is absent.
10. Cancel the proposal and verify no data changes.
11. Apply it and verify exactly one derived watchlist is created.
12. Confirm the AI Recommended badge, lineage banner, and View Analysis link.
13. Add a stock manually and confirm AI Recommended · Modified plus a Manual
    item label.
14. Navigate from the derived list to Chart and Fundamentals using existing
    recent-ticker behavior.
15. Export both the analysis and watchlist PDFs and open them from Reports.

## 15. Implementation sequence

1. **Foundation:** Add SDK/keychain dependencies, provider interfaces, safe
   error mapping, strict schemas, and deterministic fakes.
2. **Credential flow:** Implement Keychain-backed endpoints, environment
   fallback, Settings UI, and security tests.
3. **Persistence:** Add analysis, stock-result, message, revision, proposal, and
   watchlist-lineage schemas with migrations and repository tests.
4. **Mocked workflow:** Implement durable orchestration and all API endpoints
   against a fake provider before making paid calls.
5. **OpenAI workflow:** Add PDF upload, structured per-stock Responses calls,
   web research, citations, bounded concurrency, synthesis, and cleanup.
6. **Analysis UI:** Add routes, navigation, history, progress, ranking, stock
   detail, state restoration, and Watchlists-page launch action.
7. **Conversation and revisions:** Add persistent follow-ups, structured impact,
   revision creation, diffs, and historical revision navigation.
8. **Refined watchlists:** Add default selection, editable proposal, approval,
   idempotent creation, lineage, badges, modified state, and View Analysis.
9. **Reports:** Add analysis PDF, watchlist provenance, and Reports-page
   integration.
10. **Verification:** Run focused tests, full backend tests, frontend tests,
    production UI build, and one explicitly approved live smoke analysis with a
    small watchlist.

Each phase should be independently testable and committed in a reviewable unit.
Real API calls must remain opt-in during development and tests.

## 16. Definition of done

The feature is complete when:

- every finalized decision in Section 2 is implemented;
- all version-1 user flows work after refresh, navigation, and backend restart;
- a real small-list analysis succeeds with `gpt-5.6-terra` and medium
  reasoning;
- current web findings display saved citations when enabled;
- no key or authorization value appears in browser storage, API output, logs,
  reports, or Git;
- partial failures are recoverable without losing completed stock results;
- follow-ups create recommendation revisions only when appropriate;
- refined watchlists always use the latest revision and require confirmation;
- AI provenance remains visible after manual changes;
- existing watchlist, Chart, Fundamentals, Journal, scanner, and report behavior
  remains intact; and
- backend tests, frontend tests, and the production UI build pass.

## 17. Official OpenAI references

- GPT-5.6 Terra capabilities and supported tools:
  <https://developers.openai.com/api/docs/models/gpt-5.6-terra>
- API authentication and server-side key handling:
  <https://developers.openai.com/api/reference/overview>
- Responses API, conversation state, tools, and structured output:
  <https://developers.openai.com/api/reference/cli/resources/responses/methods/create>
- File inputs:
  <https://developers.openai.com/api/docs/guides/file-inputs>

There are no remaining product-design decisions blocking implementation.
Low-level names and migrations may be adjusted to fit existing code conventions
without changing the approved behavior above.
