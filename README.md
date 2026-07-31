# BambuLab-FilamentInventory

Polls Bambu Lab's cloud print-history API every 5 minutes and logs each
finished/failed/cancelled print's per-colour filament weight to a Google
Sheet.

## Setup

1. `pip install -r requirements.txt`
2. Create a Google Cloud service account with Sheets API access, download
   its JSON key, save it as `credentials.json` in the project root.
3. Copy `.env.example` to `.env` and fill in `BAMBU_EMAIL` and
   `BAMBU_PASSWORD`. Leave `SPREADSHEET_ID` empty on first run.
4. Run: `python -m bambu_inventory.main`
   - First run prompts for an emailed verification code to complete Bambu
     login, then creates a new spreadsheet and prints its ID — copy that
     ID into `.env` as `SPREADSHEET_ID` so future runs reuse the same sheet.
5. Leave the process running (or wire it to Windows Task Scheduler as a
   background/startup task) to keep logging new prints as they finish.

## Verifying task status codes against your account

`task_mapper.py` classifies task status using values documented by the
community (`RUNNING`, `FINISH`, `FAILED`). Before relying on this
unattended, confirm your account returns the same values:

```python
from dotenv import load_dotenv
import os
from bambu_inventory.bambu_client import BambuClient

load_dotenv()
client = BambuClient(os.environ["BAMBU_EMAIL"], os.environ["BAMBU_PASSWORD"], ".bambu_token.json")
for task in client.get_tasks(limit=20):
    print(task["id"], task["status"], task["title"])
```

If your account shows different status strings (e.g. for a user-cancelled
print), add them to `RUNNING_STATUSES` or `STATUS_LABELS` in
`src/bambu_inventory/task_mapper.py`.
