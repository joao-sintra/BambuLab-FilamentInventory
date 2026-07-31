# Filament Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Poll Bambu Lab's cloud print-history API every 5 minutes and log each finished/failed/cancelled print's per-colour filament weight as rows in a Google Sheet.

**Architecture:** Single Python process. Pure/testable logic (task-status classification, row mapping, dedup) lives in small modules with no network I/O; thin client wrappers (`bambu_client.py`, `sheets_client.py`) handle the actual HTTP/API calls and are tested with mocked responses. `main.py` wires the poll loop.

**Tech Stack:** Python 3.11+, `requests` (Bambu HTTP), `google-api-python-client` + `google-auth` (Sheets), `python-dotenv` (config), `pytest` (tests).

## Global Constraints

- Region: global only (`api.bambulab.com`) — per spec, out of scope: `.cn`.
- No live API calls in tests — all Bambu/Google calls mocked with fixture JSON.
- Secrets never committed: `.env`, `credentials.json`, `.bambu_token.json`, `state.json` all gitignored.
- State file only advances after a confirmed successful sheet write (crash-safe, no data loss — re-poll is safe, duplicate writes are not).
- Task status codes/strings from the real Bambu API are not 100% confirmed from docs alone — Task 6 includes a debug-dump step against the user's real account to verify constants in `task_mapper.py` before relying on the poll loop unattended.

---

## File Structure

```
BambuLab-FilamentInventory/
├── .env.example
├── .gitignore
├── requirements.txt
├── src/
│   └── bambu_inventory/
│       ├── __init__.py
│       ├── state.py           # last-seen task ID persistence
│       ├── task_mapper.py      # pure: classify + map task JSON -> sheet rows
│       ├── bambu_client.py     # HTTP: login, verify code, token cache, get_tasks
│       ├── sheets_client.py    # Google Sheets: ensure sheet exists, append rows
│       └── main.py             # poll loop wiring
└── tests/
    ├── fixtures/
    │   └── tasks_response.json
    ├── test_state.py
    ├── test_task_mapper.py
    ├── test_bambu_client.py
    └── test_sheets_client.py
```

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/bambu_inventory/__init__.py`

**Interfaces:**
- Produces: nothing importable yet — sets up the environment later tasks run in.

- [ ] **Step 1: Create `requirements.txt`**

```
requests>=2.31
google-api-python-client>=2.100
google-auth>=2.23
python-dotenv>=1.0
pytest>=7.4
```

- [ ] **Step 2: Create `.env.example`**

```
BAMBU_EMAIL=
BAMBU_PASSWORD=
SPREADSHEET_ID=
POLL_INTERVAL_SEC=300
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
credentials.json
.bambu_token.json
state.json
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Create `src/bambu_inventory/__init__.py`** (empty file)

- [ ] **Step 5: Install dependencies and verify pytest runs**

Run: `pip install -r requirements.txt && pytest --collect-only`
Expected: `no tests ran` (collection succeeds, no errors)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore src/bambu_inventory/__init__.py
git commit -m "chore: scaffold project structure and dependencies"
```

---

### Task 2: State store (last-seen task ID persistence)

**Files:**
- Create: `src/bambu_inventory/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces:
  - `class StateStore(path: str)`
  - `StateStore.get_last_seen_id() -> str | None`
  - `StateStore.set_last_seen_id(task_id: str) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_state.py
import json
import os
from bambu_inventory.state import StateStore


def test_get_last_seen_id_returns_none_when_file_missing(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.get_last_seen_id() is None


def test_set_then_get_last_seen_id_roundtrips(tmp_path):
    path = str(tmp_path / "state.json")
    store = StateStore(path)
    store.set_last_seen_id("12345")
    assert store.get_last_seen_id() == "12345"


def test_set_last_seen_id_persists_to_disk(tmp_path):
    path = str(tmp_path / "state.json")
    store = StateStore(path)
    store.set_last_seen_id("999")

    reloaded = StateStore(path)
    assert reloaded.get_last_seen_id() == "999"


def test_set_last_seen_id_overwrites_previous_value(tmp_path):
    path = str(tmp_path / "state.json")
    store = StateStore(path)
    store.set_last_seen_id("1")
    store.set_last_seen_id("2")
    assert store.get_last_seen_id() == "2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bambu_inventory.state'` (or `state.py` missing)

- [ ] **Step 3: Write minimal implementation**

```python
# src/bambu_inventory/state.py
import json
import os


class StateStore:
    def __init__(self, path: str):
        self._path = path

    def get_last_seen_id(self) -> str | None:
        if not os.path.exists(self._path):
            return None
        with open(self._path, "r") as f:
            data = json.load(f)
        return data.get("last_seen_task_id")

    def set_last_seen_id(self, task_id: str) -> None:
        with open(self._path, "w") as f:
            json.dump({"last_seen_task_id": task_id}, f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/bambu_inventory/state.py tests/test_state.py
git commit -m "feat: add state store for last-seen task id"
```

---

### Task 3: Task mapper (pure logic — classification + row mapping)

**Files:**
- Create: `src/bambu_inventory/task_mapper.py`
- Create: `tests/fixtures/tasks_response.json`
- Test: `tests/test_task_mapper.py`

**Interfaces:**
- Consumes: nothing (pure functions over plain dicts/lists)
- Produces:
  - `is_terminal_status(status: str) -> bool`
  - `status_label(status: str) -> str` (returns `"finished"`, `"failed"`, or `"unknown"`)
  - `filter_new_terminal_tasks(tasks: list[dict], last_seen_id: str | None) -> list[dict]`
  - `task_to_rows(task: dict) -> list[dict]` — each row dict has keys:
    `date`, `print_name`, `printer`, `status`, `duration_min`, `ams_slot`,
    `filament_type`, `colour_hex`, `weight_g`, `task_id`

- [ ] **Step 1: Create fixture JSON**

```json
// tests/fixtures/tasks_response.json
{
  "hits": [
    {
      "id": "1003",
      "title": "Running Print",
      "deviceName": "X1C-A",
      "status": "RUNNING",
      "startTime": "2026-07-31T10:00:00Z",
      "costTime": 0,
      "amsDetailMapping": []
    },
    {
      "id": "1002",
      "title": "Two Color Vase",
      "deviceName": "X1C-A",
      "status": "FAILED",
      "startTime": "2026-07-30T09:00:00Z",
      "costTime": 1800,
      "amsDetailMapping": [
        {
          "amsId": 0,
          "slotId": 1,
          "filamentType": "PLA",
          "targetColor": "FF0000FF",
          "weight": 12.5
        },
        {
          "amsId": 0,
          "slotId": 2,
          "filamentType": "PLA",
          "targetColor": "0000FFFF",
          "weight": 8.25
        }
      ]
    },
    {
      "id": "1001",
      "title": "Single Color Bracket",
      "deviceName": "X1C-A",
      "status": "FINISH",
      "startTime": "2026-07-29T08:00:00Z",
      "costTime": 3600,
      "amsDetailMapping": [
        {
          "amsId": 0,
          "slotId": 0,
          "filamentType": "PETG",
          "targetColor": "00FF00FF",
          "weight": 20.0
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_task_mapper.py
import json
import os
from bambu_inventory.task_mapper import (
    is_terminal_status,
    status_label,
    filter_new_terminal_tasks,
    task_to_rows,
)

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "tasks_response.json")


def load_tasks():
    with open(FIXTURE_PATH) as f:
        return json.load(f)["hits"]


def test_is_terminal_status_false_for_running():
    assert is_terminal_status("RUNNING") is False


def test_is_terminal_status_true_for_finish_and_failed():
    assert is_terminal_status("FINISH") is True
    assert is_terminal_status("FAILED") is True


def test_status_label_maps_known_values():
    assert status_label("FINISH") == "finished"
    assert status_label("FAILED") == "failed"


def test_status_label_returns_unknown_for_unrecognized_value():
    assert status_label("SOMETHING_NEW") == "unknown"


def test_filter_new_terminal_tasks_excludes_running():
    tasks = load_tasks()
    result = filter_new_terminal_tasks(tasks, last_seen_id=None)
    ids = [t["id"] for t in result]
    assert "1003" not in ids


def test_filter_new_terminal_tasks_excludes_already_seen():
    tasks = load_tasks()
    result = filter_new_terminal_tasks(tasks, last_seen_id="1002")
    ids = [t["id"] for t in result]
    assert ids == []


def test_filter_new_terminal_tasks_returns_only_newer_than_last_seen():
    tasks = load_tasks()
    result = filter_new_terminal_tasks(tasks, last_seen_id="1001")
    ids = [t["id"] for t in result]
    assert ids == ["1002"]


def test_task_to_rows_expands_multi_color_task():
    tasks = load_tasks()
    task = next(t for t in tasks if t["id"] == "1002")
    rows = task_to_rows(task)
    assert len(rows) == 2
    assert rows[0]["task_id"] == "1002"
    assert rows[0]["print_name"] == "Two Color Vase"
    assert rows[0]["status"] == "failed"
    assert rows[0]["duration_min"] == 30
    assert rows[0]["ams_slot"] == "0-1"
    assert rows[0]["filament_type"] == "PLA"
    assert rows[0]["colour_hex"] == "FF0000FF"
    assert rows[0]["weight_g"] == 12.5
    assert rows[1]["ams_slot"] == "0-2"
    assert rows[1]["weight_g"] == 8.25


def test_task_to_rows_single_color_task():
    tasks = load_tasks()
    task = next(t for t in tasks if t["id"] == "1001")
    rows = task_to_rows(task)
    assert len(rows) == 1
    assert rows[0]["status"] == "finished"
    assert rows[0]["duration_min"] == 60
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_task_mapper.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bambu_inventory.task_mapper'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/bambu_inventory/task_mapper.py

# NOTE: status strings confirmed from community docs for RUNNING/FINISH/FAILED.
# Verify against a real account (see Task 6 debug-dump step) and extend this
# set if the live API returns other non-terminal states (e.g. "PREPARE",
# "SLICING") or other terminal labels.
RUNNING_STATUSES = {"RUNNING", "PREPARE", "SLICING"}

STATUS_LABELS = {
    "FINISH": "finished",
    "FAILED": "failed",
}


def is_terminal_status(status: str) -> bool:
    return status not in RUNNING_STATUSES


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, "unknown")


def filter_new_terminal_tasks(tasks: list[dict], last_seen_id: str | None) -> list[dict]:
    result = []
    for task in tasks:
        if not is_terminal_status(task["status"]):
            continue
        if last_seen_id is not None and task["id"] <= last_seen_id:
            continue
        result.append(task)
    return result


def task_to_rows(task: dict) -> list[dict]:
    rows = []
    for entry in task.get("amsDetailMapping", []):
        rows.append({
            "date": task["startTime"],
            "print_name": task["title"],
            "printer": task["deviceName"],
            "status": status_label(task["status"]),
            "duration_min": task["costTime"] // 60,
            "ams_slot": f'{entry["amsId"]}-{entry["slotId"]}',
            "filament_type": entry["filamentType"],
            "colour_hex": entry["targetColor"],
            "weight_g": entry["weight"],
            "task_id": task["id"],
        })
    return rows
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_task_mapper.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add src/bambu_inventory/task_mapper.py tests/fixtures/tasks_response.json tests/test_task_mapper.py
git commit -m "feat: add pure task classification and row-mapping logic"
```

---

### Task 4: Bambu client (login, token cache, get_tasks)

**Files:**
- Create: `src/bambu_inventory/bambu_client.py`
- Test: `tests/test_bambu_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (network layer only)
- Produces:
  - `class BambuClient(email: str, password: str, token_path: str)`
  - `BambuClient.login(verify_code_prompt: callable[[], str]) -> None` — performs email+password login; if API responds requiring a verification code, calls `verify_code_prompt()` to obtain it and completes the second call; saves `{"token": ..., "refresh_token": ...}` to `token_path`.
  - `BambuClient.get_tasks(limit: int = 20) -> list[dict]` — returns the `hits` list from `/v1/user-service/my/tasks`; raises `AuthExpiredError` on a 401 response.
  - `class AuthExpiredError(Exception)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_bambu_client.py
import json
from unittest.mock import patch, MagicMock
from bambu_inventory.bambu_client import BambuClient, AuthExpiredError


def test_login_without_verification_saves_token(tmp_path):
    token_path = str(tmp_path / "token.json")
    client = BambuClient("a@b.com", "pw", token_path)

    login_response = MagicMock(status_code=200)
    login_response.json.return_value = {"accessToken": "tok123", "refreshToken": "ref123"}

    with patch("bambu_inventory.bambu_client.requests.post", return_value=login_response) as mock_post:
        client.login(verify_code_prompt=lambda: (_ for _ in ()).throw(AssertionError("should not be called")))

    assert mock_post.call_count == 1
    with open(token_path) as f:
        saved = json.load(f)
    assert saved == {"token": "tok123", "refresh_token": "ref123"}


def test_login_with_verification_code_calls_second_endpoint(tmp_path):
    token_path = str(tmp_path / "token.json")
    client = BambuClient("a@b.com", "pw", token_path)

    needs_code_response = MagicMock(status_code=400)
    needs_code_response.json.return_value = {"loginType": "verifyCode"}

    verified_response = MagicMock(status_code=200)
    verified_response.json.return_value = {"accessToken": "tok456", "refreshToken": "ref456"}

    with patch("bambu_inventory.bambu_client.requests.post", side_effect=[needs_code_response, verified_response]) as mock_post:
        client.login(verify_code_prompt=lambda: "654321")

    assert mock_post.call_count == 2
    with open(token_path) as f:
        saved = json.load(f)
    assert saved == {"token": "tok456", "refresh_token": "ref456"}


def test_get_tasks_returns_hits_list(tmp_path):
    token_path = str(tmp_path / "token.json")
    with open(token_path, "w") as f:
        json.dump({"token": "tok123", "refresh_token": "ref123"}, f)
    client = BambuClient("a@b.com", "pw", token_path)

    tasks_response = MagicMock(status_code=200)
    tasks_response.json.return_value = {"hits": [{"id": "1"}, {"id": "2"}]}

    with patch("bambu_inventory.bambu_client.requests.get", return_value=tasks_response) as mock_get:
        result = client.get_tasks(limit=20)

    assert result == [{"id": "1"}, {"id": "2"}]
    called_headers = mock_get.call_args.kwargs["headers"]
    assert called_headers["Authorization"] == "Bearer tok123"


def test_get_tasks_raises_auth_expired_on_401(tmp_path):
    token_path = str(tmp_path / "token.json")
    with open(token_path, "w") as f:
        json.dump({"token": "expired", "refresh_token": "ref123"}, f)
    client = BambuClient("a@b.com", "pw", token_path)

    unauthorized_response = MagicMock(status_code=401)

    with patch("bambu_inventory.bambu_client.requests.get", return_value=unauthorized_response):
        try:
            client.get_tasks()
            assert False, "expected AuthExpiredError"
        except AuthExpiredError:
            pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_bambu_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bambu_inventory.bambu_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/bambu_inventory/bambu_client.py
import json
import requests

BASE_URL = "https://api.bambulab.com"


class AuthExpiredError(Exception):
    pass


class BambuClient:
    def __init__(self, email: str, password: str, token_path: str):
        self._email = email
        self._password = password
        self._token_path = token_path

    def login(self, verify_code_prompt) -> None:
        response = requests.post(
            f"{BASE_URL}/v1/user-service/user/login",
            json={"account": self._email, "password": self._password},
        )
        data = response.json()

        if response.status_code != 200 or data.get("loginType") == "verifyCode":
            code = verify_code_prompt()
            response = requests.post(
                f"{BASE_URL}/v1/user-service/user/login",
                json={"account": self._email, "code": code},
            )
            data = response.json()

        self._save_token(data["accessToken"], data["refreshToken"])

    def _save_token(self, token: str, refresh_token: str) -> None:
        with open(self._token_path, "w") as f:
            json.dump({"token": token, "refresh_token": refresh_token}, f)

    def _load_token(self) -> str:
        with open(self._token_path) as f:
            return json.load(f)["token"]

    def get_tasks(self, limit: int = 20) -> list[dict]:
        token = self._load_token()
        response = requests.get(
            f"{BASE_URL}/v1/user-service/my/tasks",
            params={"limit": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            raise AuthExpiredError("Bambu token expired or invalid")
        return response.json()["hits"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_bambu_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/bambu_inventory/bambu_client.py tests/test_bambu_client.py
git commit -m "feat: add Bambu cloud client with login and task fetch"
```

---

### Task 5: Sheets client (ensure spreadsheet, append rows)

**Files:**
- Create: `src/bambu_inventory/sheets_client.py`
- Test: `tests/test_sheets_client.py`

**Interfaces:**
- Consumes: row dicts shaped like `task_to_rows()` output from Task 3 (keys: `date`, `print_name`, `printer`, `status`, `duration_min`, `ams_slot`, `filament_type`, `colour_hex`, `weight_g`, `task_id`)
- Produces:
  - `class SheetsClient(credentials_path: str, spreadsheet_id: str | None)`
  - `SheetsClient.ensure_spreadsheet() -> str` — returns spreadsheet ID, creating a new spreadsheet + `PrintLog` tab + header row if `spreadsheet_id` was `None`
  - `SheetsClient.append_rows(rows: list[dict]) -> None`
  - `HEADER = ["Date", "Print Name", "Printer", "Status", "Duration (min)", "AMS Slot", "Filament Type", "Colour (hex)", "Weight (g)", "Task ID"]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sheets_client.py
from unittest.mock import patch, MagicMock
from bambu_inventory.sheets_client import SheetsClient, HEADER


def make_client_with_mock_service(spreadsheet_id):
    with patch("bambu_inventory.sheets_client.build") as mock_build, \
         patch("bambu_inventory.sheets_client.service_account.Credentials.from_service_account_file"):
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        client = SheetsClient("creds.json", spreadsheet_id)
        return client, mock_service


def test_ensure_spreadsheet_creates_new_when_id_is_none():
    client, mock_service = make_client_with_mock_service(None)
    mock_service.spreadsheets().create().execute.return_value = {"spreadsheetId": "new-id-123"}

    result = client.ensure_spreadsheet()

    assert result == "new-id-123"
    mock_service.spreadsheets().create.assert_called()
    mock_service.spreadsheets().values().update.assert_called()


def test_ensure_spreadsheet_returns_existing_id_without_creating():
    client, mock_service = make_client_with_mock_service("existing-id")

    result = client.ensure_spreadsheet()

    assert result == "existing-id"
    mock_service.spreadsheets().create.assert_not_called()


def test_append_rows_sends_values_in_header_order():
    client, mock_service = make_client_with_mock_service("existing-id")
    row = {
        "date": "2026-07-30T09:00:00Z",
        "print_name": "Two Color Vase",
        "printer": "X1C-A",
        "status": "failed",
        "duration_min": 30,
        "ams_slot": "0-1",
        "filament_type": "PLA",
        "colour_hex": "FF0000FF",
        "weight_g": 12.5,
        "task_id": "1002",
    }

    client.append_rows([row])

    append_call = mock_service.spreadsheets().values().append
    append_call.assert_called_once()
    sent_values = append_call.call_args.kwargs["body"]["values"]
    assert sent_values == [[
        "2026-07-30T09:00:00Z", "Two Color Vase", "X1C-A", "failed", 30,
        "0-1", "PLA", "FF0000FF", 12.5, "1002",
    ]]


def test_header_constant_matches_expected_columns():
    assert HEADER == [
        "Date", "Print Name", "Printer", "Status", "Duration (min)",
        "AMS Slot", "Filament Type", "Colour (hex)", "Weight (g)", "Task ID",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sheets_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bambu_inventory.sheets_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/bambu_inventory/sheets_client.py
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_NAME = "PrintLog"
HEADER = [
    "Date", "Print Name", "Printer", "Status", "Duration (min)",
    "AMS Slot", "Filament Type", "Colour (hex)", "Weight (g)", "Task ID",
]

ROW_KEYS = [
    "date", "print_name", "printer", "status", "duration_min",
    "ams_slot", "filament_type", "colour_hex", "weight_g", "task_id",
]


class SheetsClient:
    def __init__(self, credentials_path: str, spreadsheet_id: str | None):
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        self._service = build("sheets", "v4", credentials=creds)
        self._spreadsheet_id = spreadsheet_id

    def ensure_spreadsheet(self) -> str:
        if self._spreadsheet_id:
            return self._spreadsheet_id

        result = self._service.spreadsheets().create(
            body={
                "properties": {"title": "Bambu Filament Inventory"},
                "sheets": [{"properties": {"title": SHEET_NAME}}],
            }
        ).execute()
        spreadsheet_id = result["spreadsheetId"]

        self._service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [HEADER]},
        ).execute()

        self._spreadsheet_id = spreadsheet_id
        return spreadsheet_id

    def append_rows(self, rows: list[dict]) -> None:
        values = [[row[key] for key in ROW_KEYS] for row in rows]
        self._service.spreadsheets().values().append(
            spreadsheetId=self._spreadsheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sheets_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/bambu_inventory/sheets_client.py tests/test_sheets_client.py
git commit -m "feat: add Google Sheets client for spreadsheet creation and row append"
```

---

### Task 6: Main poll loop + README setup docs

**Files:**
- Create: `src/bambu_inventory/main.py`
- Modify: `README.md`

**Interfaces:**
- Consumes:
  - `StateStore` from Task 2 (`get_last_seen_id`, `set_last_seen_id`)
  - `filter_new_terminal_tasks`, `task_to_rows` from Task 3
  - `BambuClient`, `AuthExpiredError` from Task 4
  - `SheetsClient` from Task 5
- Produces: `main()` entry point, runnable via `python -m bambu_inventory.main`

This task wires existing tested components together; the loop itself is
integration glue, verified by manual run against the debug-dump step below
rather than further unit tests (no new business logic is introduced).

- [ ] **Step 1: Write `main.py`**

```python
# src/bambu_inventory/main.py
import os
import time
import logging
from dotenv import load_dotenv

from bambu_inventory.state import StateStore
from bambu_inventory.task_mapper import filter_new_terminal_tasks, task_to_rows
from bambu_inventory.bambu_client import BambuClient, AuthExpiredError
from bambu_inventory.sheets_client import SheetsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bambu_inventory")


def prompt_for_verification_code() -> str:
    return input("Enter the verification code emailed to you: ").strip()


def run_poll_cycle(bambu: BambuClient, sheets: SheetsClient, state: StateStore) -> None:
    try:
        tasks = bambu.get_tasks(limit=20)
    except AuthExpiredError:
        log.warning("Bambu token expired, re-authenticating (may require emailed code)")
        bambu.login(verify_code_prompt=prompt_for_verification_code)
        tasks = bambu.get_tasks(limit=20)

    last_seen_id = state.get_last_seen_id()
    new_tasks = filter_new_terminal_tasks(tasks, last_seen_id)
    if not new_tasks:
        return

    # tasks are returned newest-first; process oldest-first so state
    # advances monotonically and a mid-loop crash re-polls safely
    new_tasks.reverse()

    for task in new_tasks:
        rows = task_to_rows(task)
        if rows:
            sheets.append_rows(rows)
        state.set_last_seen_id(task["id"])
        log.info(f"Logged task {task['id']} ({task['title']}) - {len(rows)} row(s)")


def main() -> None:
    load_dotenv()
    email = os.environ["BAMBU_EMAIL"]
    password = os.environ["BAMBU_PASSWORD"]
    spreadsheet_id = os.environ.get("SPREADSHEET_ID") or None
    poll_interval = int(os.environ.get("POLL_INTERVAL_SEC", "300"))

    bambu = BambuClient(email, password, token_path=".bambu_token.json")
    if not os.path.exists(".bambu_token.json"):
        bambu.login(verify_code_prompt=prompt_for_verification_code)

    sheets = SheetsClient("credentials.json", spreadsheet_id)
    resolved_id = sheets.ensure_spreadsheet()
    if not spreadsheet_id:
        log.info(f"Created new spreadsheet. Save this to .env as SPREADSHEET_ID={resolved_id}")

    state = StateStore("state.json")

    log.info(f"Starting poll loop, interval={poll_interval}s")
    while True:
        try:
            run_poll_cycle(bambu, sheets, state)
        except Exception:
            log.exception("Poll cycle failed, will retry next interval")
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update `README.md` with setup instructions**

```markdown
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
```

- [ ] **Step 3: Manual smoke test**

Run: `python -m bambu_inventory.main`
Expected: prompts for verification code (first run), logs "Starting poll
loop", then either "Logged task ..." or silently waits until the next
interval if no new terminal tasks exist. Ctrl+C to stop.

- [ ] **Step 4: Run full test suite to confirm nothing broke**

Run: `pytest -v`
Expected: all tests from Tasks 2-5 pass (17 total)

- [ ] **Step 5: Commit**

```bash
git add src/bambu_inventory/main.py README.md
git commit -m "feat: wire poll loop entry point and add setup docs"
```

---

## Self-Review Notes

- **Spec coverage:** architecture (Tasks 1-6), sheet schema (Task 5 `HEADER`),
  auth flow for both Bambu and Google (Tasks 4-6), error handling — retry
  on network errors, re-auth on 401, state advances only after successful
  write (Task 6 `run_poll_cycle`), config via `.env` (Tasks 1, 6), testing
  with mocked HTTP/fixtures (Tasks 2-5) are all covered. Out-of-scope items
  from the spec (spool-level inventory, `.cn` region, multi-account) are
  correctly not implemented here.
- **Placeholder scan:** none found — every step has runnable code.
- **Type consistency:** `task_to_rows()` row dict keys (Task 3) match
  `ROW_KEYS` order in `sheets_client.py` (Task 5) and the `HEADER` column
  order one-to-one.
