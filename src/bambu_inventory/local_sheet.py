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

INVENTORY_SHEET_NAME = "Filament Inventory"
INVENTORY_HEADER = [
    "Filament Type", "Colour", "Total Weight (g)", "Remaining Weight (g)",
]
# column indices (1-based, openpyxl convention) within INVENTORY_HEADER
INVENTORY_COL_FILAMENT_TYPE = 1
INVENTORY_COL_COLOUR = 2
INVENTORY_COL_REMAINING = 4


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

    def deduct_filament_usage(self, rows: list[dict]) -> None:
        workbook = load_workbook(self._path)
        if INVENTORY_SHEET_NAME not in workbook.sheetnames:
            sheet = workbook.create_sheet(INVENTORY_SHEET_NAME)
            sheet.append(INVENTORY_HEADER)
        else:
            sheet = workbook[INVENTORY_SHEET_NAME]

        for row in rows:
            match = None
            for existing_row in sheet.iter_rows(min_row=2):
                if (
                    existing_row[INVENTORY_COL_FILAMENT_TYPE - 1].value == row["filament_type"]
                    and existing_row[INVENTORY_COL_COLOUR - 1].value == row["colour_hex"]
                ):
                    match = existing_row
                    break

            if match is not None:
                remaining_cell = match[INVENTORY_COL_REMAINING - 1]
                current = remaining_cell.value or 0
                remaining_cell.value = current - row["weight_g"]
            else:
                sheet.append([
                    row["filament_type"], row["colour_hex"], "", -row["weight_g"],
                ])

        workbook.save(self._path)
