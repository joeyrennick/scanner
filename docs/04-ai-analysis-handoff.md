# AI Analysis and Refined Watchlists Handoff

Last updated: 2026-08-29

## Status

Design discussion is complete enough to begin implementation. No AI Analysis
code has been implemented yet.

Working directory: `/Users/joe.rennick/scanner`

This document records the agreed design for submitting a saved watchlist to an
OpenAI model, displaying and preserving the findings inside the scanner, and
creating a refined watchlist from the results.

## Product goal

Add a one-click **Analyze with AI** workflow to the Watchlists page. After a
one-time OpenAI API connection, the scanner should:

1. Snapshot the selected watchlist.
2. Generate its existing PDF export.
3. Submit the prompt, PDF, and structured watchlist data to the OpenAI Responses
   API.
4. Analyze every ticker and produce an ordered growth-stock ranking.
5. Show progress and results on a dedicated page inside the scanner.
6. Preserve every analysis locally as immutable history.
7. Let the user create a new refined watchlist from the ranked results after
   reviewing and approving the proposed changes.

## Important terminology and authentication boundary

The feature should be named **AI Analysis** in the scanner. It uses an OpenAI
model through the API; it does not control ChatGPT Web and its conversations do
not automatically appear at `chatgpt.com`.

- Never request or store a ChatGPT email, password, browser cookie, or session
  token.
- A ChatGPT login or subscription does not authenticate OpenAI API requests.
- The user supplies an OpenAI API key once.
- API billing is separate from a ChatGPT subscription.
- The API key must be available only to the backend. Never return it through an
  API response or place it in frontend local storage.
- Prefer macOS Keychain (potentially through Python `keyring`) for the OpenAI
  API key. The existing `SQLiteSecretStore` can be reused as a fallback, but its
  database and local encryption-key file are colocated and provide weaker
  protection than the operating-system credential store.

Official references:

- API authentication and server-side secret handling:
  <https://developers.openai.com/api/reference/overview>
- PDF and other file inputs:
  <https://developers.openai.com/api/docs/guides/file-inputs>
- Responses API tools and custom function calls:
  <https://developers.openai.com/api/reference/cli/resources/responses/methods/create>

## Default prompt

Preserve the user's requested primary prompt:

> I'm going to give you the full list (including what I already sent you).
> Analyze the stocks one by one on the list and then rate them in order with the
> best being at the top. I'm looking for high potential growth stocks.

The backend should add transparent, versioned developer instructions requiring:

- a consistent scoring methodology across all stocks;
- current research with source citations when web research is enabled;
- clear separation between scanner-provided values and externally researched
  facts;
- explicit evaluation of growth, valuation, financial quality, catalysts, and
  risk;
- no invented values;
- an `insufficient_evidence` result when the available evidence is inadequate;
- structured output that the UI can validate and render predictably; and
- a visible disclaimer that the result is research support, not investment
  advice.

## Recommended user flow

### First use

1. Select a watchlist and click **Analyze with AI**.
2. Navigate to `/ai-analysis/new?watchlistId=<id>`.
3. If no valid API key exists, show a blocking **Connect OpenAI API** panel on
   the AI Analysis page.
4. The panel includes:
   - a link to create/manage an OpenAI API key;
   - a masked API-key field;
   - **Save and Verify**;
   - a short explanation of separate API billing and local secret storage.
5. Save the credential on the backend and verify it with a low-cost API
   authentication check.
6. Automatically resume the pending analysis after successful verification.

### Returning use

1. Click **Analyze with AI** for the active watchlist.
2. Immediately create an immutable watchlist snapshot and an analysis job.
3. Navigate to `/ai-analysis/<analysis-id>`.
4. Display progress while the backend runs the analysis.
5. Persist partial progress so refreshes and navigation do not lose the run.

## AI Analysis page

Add **AI Analysis** to the main navigation. Recommended routes:

- `/ai-analysis` — historical analyses across all watchlists;
- `/ai-analysis/new?watchlistId=<id>` — connection/preflight and run creation;
- `/ai-analysis/<analysis-id>` — one saved analysis;
- a comparison route can be added later if comparison requires more screen
  space.

Recommended layout:

### History panel

A clickable list grouped or filterable by watchlist. Each entry shows:

- watchlist name;
- analysis date and time;
- completed ticker count;
- top-ranked ticker when available;
- model;
- complete, running, failed, or cancelled status.

Selecting an entry restores the exact saved findings and watchlist snapshot.
The result must remain accessible even if the source watchlist is later renamed,
changed, or deleted.

### Analysis header and actions

- Watchlist name and snapshot timestamp
- Model and analysis-instruction version
- Status and overall progress
- **Cancel**, **Retry**, **Re-analyze**, **Create Refined Watchlist**, and
  **Export PDF** actions as applicable
- OpenAI connection status with a link to Settings

### Progress view

Use a durable progress display modeled after the existing scanner progress UI.
Show stages such as:

- Preparing watchlist snapshot
- Generating analysis package
- Analyzing MCD (7 of 24)
- Building final ranking
- Saving report

The UI should continue polling or streaming after refresh and should clearly
identify partial failures rather than discarding the entire run.

### Results view

Display a sortable ranking table with at least:

- Rank
- Ticker
- Overall score
- Growth score
- Valuation assessment
- Risk
- Confidence
- Short recommendation

Selecting a ticker shows its detailed thesis, growth evidence, valuation,
catalysts, risks, confidence explanation, cited sources, and the scanner data
used for the evaluation.

### Follow-up conversation

Preserve follow-up questions and visible model responses under the analysis.
Follow-ups remain scoped to the immutable analysis snapshot unless the user
explicitly starts a new analysis with current watchlist data.

## Preserving findings

The scanner's local database is the canonical record. Do not rely on OpenAI
retaining a response indefinitely.

Each run should preserve:

- source watchlist ID when it still exists;
- source watchlist name;
- immutable watchlist snapshot;
- generated PDF report ID/path or reproducible report payload;
- primary prompt and developer-instruction version;
- requested model and actual model returned;
- visible narrative response;
- validated structured result;
- per-stock results and ranking;
- citation metadata and data-as-of timestamps;
- OpenAI response/conversation identifiers when available;
- input/output token usage and other available usage metadata;
- job stage, progress, error, and retry information;
- created, started, updated, and completed timestamps; and
- all visible follow-up messages.

Do not attempt to preserve hidden chain-of-thought. Preserve only visible model
content, structured findings, tool results needed for the report, and source
metadata.

## Suggested persistence model

Exact migration details can be adjusted to match the repository's SQLite data
patterns.

### `ai_analysis_runs`

- `id`
- `source_watchlist_id` (nullable to survive watchlist deletion)
- `source_watchlist_name`
- `watchlist_snapshot_json`
- `report_id` or `report_path`
- `prompt`
- `instruction_version`
- `requested_model`
- `actual_model`
- `status`
- `stage`
- `progress_current`
- `progress_total`
- `response_text`
- `result_json`
- `openai_response_id`
- `openai_conversation_id`
- token/usage fields
- `error_code`
- `error_message`
- timestamps

### `ai_analysis_stock_results`

- `analysis_id`
- `ticker`
- `rank`
- overall/growth/valuation/risk/confidence values
- recommendation and summary
- thesis, catalysts, and risks
- source metadata JSON
- status/error for independently failed tickers

### `ai_analysis_messages`

- `id`
- `analysis_id`
- `role`
- visible `content`
- OpenAI response identifier when applicable
- timestamp

### Derived-watchlist lineage

Either add optional lineage fields to saved watchlists or create a separate
lineage table containing:

- derived saved-watchlist ID;
- source analysis ID;
- source watchlist ID/name;
- selection policy JSON;
- creation timestamp.

Each derived item should retain its AI rank, score, inclusion reason, and source
analysis ID when the existing saved-watchlist item model can be extended safely.

## Analysis execution design

One click for the user should not require one enormous model request.

1. Snapshot the watchlist before starting.
2. Generate the existing watchlist PDF.
3. Provide both the PDF and a compact structured representation of the same
   watchlist. The structured data improves numeric reliability; the PDF satisfies
   the exported-watchlist requirement and preserves presentation context.
4. For small lists, a single bounded request may be acceptable.
5. For larger lists, analyze stocks independently in bounded parallel batches,
   persist each result, and run a final synthesis over all validated per-stock
   findings.
6. Use structured output for the per-stock and final-ranking schemas.
7. Enable current web research by default for a growth-investment analysis,
   subject to an explicit run budget and tool-call limit.
8. Cache reusable recent per-stock research where the inputs and as-of date make
   reuse safe and visible.
9. A failure for one ticker should be reported as a partial failure and should
   not erase completed ticker results.
10. Final ranking must account for missing evidence rather than silently placing
    failed tickers.

## Refined watchlists

A completed analysis should offer **Create Refined Watchlist**. For version 1:

- create a new watchlist; never overwrite the source watchlist;
- select only from tickers actually analyzed in the source list;
- do not introduce new ticker ideas;
- preserve ranking and inclusion reasons;
- validate ticker symbols and remove duplicates before showing the proposal;
- require explicit user approval before writing the new watchlist.

The proposal dialog should support:

- top 5, 10, 20, or all;
- minimum overall score;
- allowed risk levels;
- include/exclude `Needs Review`;
- include only validated fundamentals;
- editable new-watchlist name;
- complete preview of included and excluded stocks with reasons.

Suggested default name:

`Growth Picks - <source watchlist> - <YYYY-MM-DD>`

The derived list is otherwise a normal saved watchlist and must retain all
existing Watchlists page behaviors, including navigation to maximized charts and
Fundamentals, adding to the Journal, deletion, filtering, sorting, persistence,
and PDF export.

## Model-initiated application actions

The OpenAI model can propose actions using strongly typed function calls, but it
does not directly manipulate the local application or database. The scanner
decides which tools exist, validates their arguments, and executes approved
operations.

Recommended version-1 boundary:

1. The model may produce a structured `watchlist_proposal`.
2. The backend validates the proposal without mutating data.
3. The UI shows an approval card and a full before/after preview.
4. The user clicks **Approve and Create**.
5. The scanner calls its existing saved-watchlist service to create the list.

Even if implemented as a custom function tool, a proposal must not perform the
write itself. A future tool could conceptually be named
`propose_watchlist_from_analysis`, with arguments for the analysis ID, name,
selection rule, and ranked ticker set.

Do not expose tools that allow the model to:

- delete or overwrite watchlists;
- remove journal entries;
- place trades;
- change scanner or credential settings;
- execute arbitrary commands; or
- bypass user approval for a side effect.

An optional **Expanded Watchlist** mode that researches and introduces new
tickers should be treated as a later, separate feature with stricter validation.

## Suggested backend API surface

Names can be adjusted to current project conventions.

### Credential management

- `GET /api/openai/credential` — configured/verified metadata only
- `PUT /api/openai/credential` — save and verify a new API key
- `POST /api/openai/credential/test` — test the stored key
- `DELETE /api/openai/credential` — remove the key

### Analyses

- `GET /api/ai/analyses` — history with watchlist/status filters
- `POST /api/ai/watchlists/{watchlist_id}/analyses` — snapshot and start
- `GET /api/ai/analyses/{analysis_id}` — full saved result/progress
- `POST /api/ai/analyses/{analysis_id}/cancel`
- `POST /api/ai/analyses/{analysis_id}/retry`
- `POST /api/ai/analyses/{analysis_id}/messages` — follow-up question
- `POST /api/ai/analyses/{analysis_id}/report` — PDF export

### Refined-watchlist proposal

- `POST /api/ai/analyses/{analysis_id}/watchlist-proposal`
- `POST /api/ai/analyses/{analysis_id}/watchlist-proposal/apply`

The apply endpoint must accept the reviewed proposal or an immutable proposal
identifier, validate it again, and be idempotent so a retry cannot create
duplicate lists.

## Expected code areas

Likely existing files to extend:

- `src/scanner/api/app.py`
- `src/scanner/api/schemas.py`
- `src/scanner/api/jobs.py`
- `src/scanner/security/secret_store.py`
- `src/scanner/data/saved_watchlists.py`
- `src/scanner/reports/saved_watchlist_report.py`
- `ui/src/App.tsx`
- `ui/src/routes.ts`
- `ui/src/api/types.ts`
- `ui/src/api/queryKeys.ts`
- `ui/src/features/watchlists/WatchlistsPage.tsx`

Likely new modules:

- `src/scanner/ai/openai_client.py`
- `src/scanner/ai/watchlist_analysis.py`
- `src/scanner/ai/prompts.py`
- `src/scanner/data/ai_analyses.py`
- `src/scanner/reports/ai_analysis_report.py`
- `ui/src/api/aiAnalyses.ts`
- `ui/src/features/ai-analysis/AIAnalysisPage.tsx`
- focused backend and frontend tests for those modules

Avoid concentrating the orchestration and persistence logic in `api/app.py`.
Keep endpoints thin and put durable workflow logic in services/data modules.

## Security, cost, and privacy requirements

- Never log the API key, full authorization header, or credential request body.
- Mask secret inputs and clear them from component state after submission.
- Provide Test, Replace, and Disconnect actions in Settings.
- Explain exactly which watchlist data will leave the local scanner.
- Record model and tool usage per run when the API provides it.
- Add configurable per-run symbol, token, and tool-call limits.
- Avoid silent automatic retries that can multiply cost.
- Show a clear error for invalid key, revoked key, missing billing, rate limit,
  context limit, network failure, and partial ticker failure.
- Do not place full API responses containing sensitive content in ordinary logs.
- Deleting a local analysis and deleting any remotely uploaded file are separate
  operations; define and test the intended cleanup behavior.

## State preservation requirements

- Clicking **Analyze with AI** remembers the source watchlist and pending action.
- Connection completion automatically resumes the intended run.
- Refreshing the page restores the active analysis and current result selection.
- Navigation away and back restores history filters, selected analysis, selected
  ticker, scroll positions, and expanded detail sections where practical.
- Sorting or filtering results must not discard the analysis selection.
- Running jobs must remain discoverable after a backend restart if durable job
  recovery is implemented; at minimum, interrupted jobs must be marked clearly
  and be retryable without losing completed per-stock results.

## Test plan

### Backend

- Credential save/status/test/delete without exposing the secret
- Invalid/revoked credential and missing-billing handling
- Watchlist snapshot immutability
- PDF and structured-data request construction
- Structured-output validation
- Small-list and batched large-list orchestration
- Partial failure, retry, cancel, and restart behavior
- History survives watchlist rename/delete
- Proposal validation and idempotent creation
- No source-watchlist mutation
- API key and authorization header redaction

### Frontend

- First-run connection and automatic resume
- Returning one-click analysis flow
- Progress, cancel, retry, and failure states
- Refresh/navigation state restoration
- Clickable history and exact-result restoration
- Per-stock detail and citation rendering
- Refined-watchlist filters and preview
- Approval required before creation
- Derived list opens through normal Watchlists workflows

### End-to-end acceptance

1. Save an API key once and restart both servers.
2. Analyze a multi-stock saved watchlist with one click.
3. Observe durable per-ticker progress.
4. Refresh mid-run and retain the active analysis.
5. Open a completed historical result after changing the source watchlist.
6. Ask a follow-up question and preserve it in the analysis history.
7. Generate a top-N, non-high-risk refined-watchlist proposal.
8. Cancel it and verify no data changes.
9. Approve it and verify exactly one new saved watchlist is created.
10. Navigate from the derived list to chart, Fundamentals, Journal, and PDF
    export using existing behavior.

## Recommended implementation sequence

1. Add OpenAI SDK dependency and a backend client abstraction that can be mocked.
2. Add secure credential endpoints and Settings UI.
3. Add durable analysis persistence and history endpoints.
4. Add analysis job orchestration with a mocked provider and structured schemas.
5. Connect real Responses API PDF/structured inputs and web research.
6. Add the AI Analysis page, routes, history, progress, and results rendering.
7. Add the Watchlists-page **Analyze with AI** action and automatic connection
   resume.
8. Add follow-up conversation persistence.
9. Add refined-watchlist proposal, preview, validation, approval, lineage, and
   idempotent creation.
10. Add AI report generation and Reports-page integration.
11. Run focused tests, full backend/frontend suites, and production build.

Keep the real OpenAI client behind an interface from the beginning. Unit and UI
tests should use deterministic fakes and must not incur API charges.

## Decisions to confirm at implementation start

The design direction is agreed; these configuration details remain open:

1. Default model and reasoning level.
2. Default maximum watchlist size or per-run spending limit.
3. Whether macOS Keychain is required for version 1 or the existing encrypted
   SQLite secret store is acceptable initially.
4. Whether web research is always enabled or is an analysis-page option. The
   recommendation is enabled by default.
5. Default refined-list rule. A reasonable starting point is top 10, excluding
   high-risk and insufficient-evidence results, without excluding `Needs Review`
   until the user chooses that filter.
6. Whether follow-up chat ships with the initial analysis release or immediately
   afterward.

## Tomorrow's starting prompt

> Work in `/Users/joe.rennick/scanner`. Read
> `docs/04-ai-analysis-handoff.md` completely, inspect the current Git status,
> and create an implementation plan for the AI Analysis and refined-watchlist
> feature. Preserve existing user changes. Do not implement until the plan and
> remaining configuration decisions have been reviewed.

## Repository note at handoff

- `.idea/` was already untracked and was not modified.
- The older root `SESSION_HANDOFF.md` was already untracked and was not modified.
- This handoff adds only `docs/04-ai-analysis-handoff.md`.
