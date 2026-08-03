# BambuLab-FilamentInventory

Polls Bambu Lab's cloud print-history API every 5 minutes and logs each
finished/failed/cancelled print's per-colour filament weight to a local
`.xlsx` spreadsheet.

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in `BAMBU_EMAIL` and
   `BAMBU_PASSWORD`. `OUTPUT_XLSX_PATH` defaults to
   `filament_inventory.xlsx` in the project root — change it if you want
   the file somewhere else.
3. Run: `python -m bambu_inventory.main`
   - First run prompts for an emailed verification code to complete Bambu
     login, then creates the spreadsheet file with a `PrintLog` tab and
     header row if it doesn't already exist.
4. Leave the process running (or wire it to Windows Task Scheduler as a
   background/startup task) to keep logging new prints as they finish.

## Google/SSO accounts (no Bambu password)

If your Bambu account signs in via Google (i.e. you have no separate Bambu
password), leave `BAMBU_PASSWORD` blank in `.env`. The script's interactive
email+password login can't work for these accounts, so you need to seed it
with a valid token manually:

1. Log into [bambulab.com](https://bambulab.com) (or the Bambu Handy app)
   using your Google account.
2. Open your browser's devtools → Network tab (in the app, use a proxy tool
   like Proxyman/Charles if devtools aren't available).
3. Find a request to `api.bambulab.com` that includes an
   `Authorization: Bearer <token>` header — that header value is your access
   token. Also look for the login/refresh response body, which contains
   `accessToken` and `refreshToken` fields — this is the same shape the
   script itself would have written, had it logged in with a password.
4. Create `.bambu_token.json` in the project root with exactly this shape:

   ```json
   {"token": "<access token>", "refresh_token": "<refresh token>"}
   ```

5. Run `python -m bambu_inventory.main` as normal. Since the token file
   already exists, the script skips interactive login and uses this token
   directly, automatically refreshing it via the refresh-token flow as it
   expires — no password ever required.

If the refresh token itself eventually expires (Bambu tokens are long-lived
but not permanent), the script will log an error asking you to repeat this
manual extraction — it cannot prompt you for a Google login itself.

## Verifying task status codes against your account

`task_mapper.py` classifies task status using an integer code (not the
string codes some community docs describe). Confirmed against a real
account: `2` = finished successfully, `3` = user-cancelled/stopped — a
genuine print-error code hasn't been observed yet. This is a safe
whitelist: only confirmed-terminal codes are treated as terminal;
unrecognized codes (e.g. an in-progress or error status not seen yet) are
skipped, not misclassified. If your account behaves differently, confirm
with:

```python
from dotenv import load_dotenv
import os
from bambu_inventory.bambu_client import BambuClient

load_dotenv()
client = BambuClient(os.environ["BAMBU_EMAIL"], os.environ.get("BAMBU_PASSWORD", ""), ".bambu_token.json")
for task in client.get_tasks(limit=20):
    print(task["id"], task["status"], task["title"])
```

If you see a status code not in `TERMINAL_STATUSES` for a print that
actually finished or failed with an error, add it to `TERMINAL_STATUSES`
and `STATUS_LABELS` in `src/bambu_inventory/task_mapper.py`.
