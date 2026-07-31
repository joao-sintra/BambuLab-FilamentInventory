from __future__ import annotations

import os

from openpyxl import Workbook, load_workbook

SHEET_NAME = "PrintLog"
HEADER = [
    "Date", "Print Name", "Printer", "Status", "Duration (min)",
    "AMS Slot", "Filament Type", "Colour (hex)", "Weight (g)", "Task ID",
]

ROW_KEYS = [
    "date", "print_name", "printer", "status", "duration_min",
    "ams_slot", "filament_type", "colour_hex", "weight_g", "task_id",
]


class LocalSheetWriter:
    def __init__(self, path: str):
        self._path = path

    def ensure_workbook(self) -> str:
        if os.path.exists(self._path):
            return self._path

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = SHEET_NAME
        sheet.append(HEADER)
        workbook.save(self._path)
        return self._path

    def append_rows(self, rows: list[dict]) -> None:
        workbook = load_workbook(self._path)
        sheet = workbook[SHEET_NAME]
        for row in rows:
            sheet.append([row[key] for key in ROW_KEYS])
        workbook.save(self._path)
