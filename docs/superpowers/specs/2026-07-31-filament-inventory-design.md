# Bambu Filament Inventory — Design

## Purpose

Track filament consumption per print (per colour/AMS slot) by polling Bambu Lab's
cloud print-history API, and log each finished/stopped print as rows in a
Google Sheet, so filament usage per spool/colour is queryable over time.

## Architecture

Single long-running Python script (local PC background process, e.g. run via
`python main.py` in a terminal, or wired to Windows Task Scheduler as a
startup task). Polls every 5 minutes (configurable). No MQTT — live telemetry
doesn't expose consumed weight; only the cloud task-history endpoint does.

Modules:

- `bambu_client.py` — handles login (`POST /v1/user-service/user/login`),
  email verification code exchange, JWT/refresh token caching, and fetching
  `GET /v1/user-service/my/tasks`.
- `state.py` — tracks the last-processed task ID in a local JSON file, so
  restarts don't re-emit rows already written to the sheet.
- `sheets_client.py` — Google Sheets API client using a service account;
  appends rows, and on first run (empty `SPREADSHEET_ID`) creates a new
  spreadsheet + `PrintLog` tab + header row.
- `main.py` — poll loop: fetch tasks, diff against last-seen ID, filter to
  terminal-status tasks (finished / failed / cancelled by user), expand each
  task's `amsDetailMapping` into one row per colour/slot, write to sheet,
  update state file.

## Data flow

1. Poll `/my/tasks?limit=20` every `POLL_INTERVAL_SEC`.
2. Compare returned task IDs against the last-seen ID stored in state file.
3. For each new task with a terminal status (not "running"/"printing"):
   - For each entry in `amsDetailMapping`, build one row.
   - Append all rows for that task in one batch call to Sheets API.
   - Update state file with the new last-seen task ID (only after a
     successful sheet write, so a crash mid-write causes a safe re-poll
     rather than data loss).

## Sheet schema

Spreadsheet created on first run (ID saved back into `.env` if not already
set). Single tab `PrintLog`, one row per colour/slot:

| Column | Source |
|---|---|
| Date | task start time |
| Print Name | task title |
| Printer | device name |
| Status | finished / failed / cancelled |
| Duration (min) | costTime |
| AMS Slot | amsId + slotId |
| Filament Type | filamentType |
| Colour (hex) | targetColor |
| Weight (g) | amsDetailMapping[].weight |
| Task ID | dedup key, not meant for manual editing |

Failed/cancelled prints are logged with their status flagged, not excluded,
so the user can filter them out in Sheets formulas if they want "actual
consumption" vs "all attempts" views.

## Auth

**Bambu Lab (global region, api.bambulab.com):**
- First run: prompt for email + password (from `.env` if present, else
  interactive prompt), call login endpoint, if it requires an emailed
  verification code, prompt for that code and complete the second call.
- Cache JWT + refresh info in `.bambu_token.json` (gitignored).
- Subsequent runs reuse the cached token. On a 401, attempt token refresh;
  if refresh fails, fall back to the interactive email+password+code flow
  (logs a clear message — this requires the user to be present).

**Google Sheets:**
- Service account key file `credentials.json` (gitignored). User creates
  the service account + key in Google Cloud Console (one-time manual step,
  documented in README) and the script needs edit access — either the
  service account creates the spreadsheet itself (owns it) or the user
  shares a pre-existing spreadsheet with the service account's email.
- `SPREADSHEET_ID` in `.env`. Empty on first run triggers auto-creation.

## Config (`.env`, gitignored)

```
BAMBU_EMAIL=
BAMBU_PASSWORD=
SPREADSHEET_ID=
POLL_INTERVAL_SEC=300
```

`.gitignore` additions: `.env`, `credentials.json`, `.bambu_token.json`,
`state.json`.

## Error handling

- Network/HTTP errors talking to either API: log and retry on the next poll
  cycle. The loop never crashes on a transient failure.
- Bambu token expired and refresh fails: log a warning that interactive
  re-auth is needed; keep retrying the poll (so the process doesn't die,
  but no new data is written until the user re-authenticates).
- Duplicate/already-seen task IDs: skipped via the state file check before
  any sheet write is attempted.
- Sheets API errors (quota, transient 5xx): log and retry next cycle;
  state file is only advanced after a confirmed successful write.

## Testing

Unit tests with mocked HTTP responses (fixture JSON matching real
`/my/tasks` payloads) covering:
- Task → row mapping, including multi-colour `amsDetailMapping` expansion.
- Dedup logic against the state file.
- Terminal-status filtering (running/printing tasks excluded).

No live API calls in the test suite.

## Out of scope

- Spool-level inventory deduction (tracking remaining grams per physical
  spool) — this design only logs consumption per print. Could be a later
  addition reading from the same sheet.
- China region (api.bambulab.cn) — global region only for now.
- Multi-user / multi-account support.
