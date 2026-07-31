from __future__ import annotations

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
