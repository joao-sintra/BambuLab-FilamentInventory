from __future__ import annotations

import logging
import os

from openpyxl import Workbook, load_workbook

log = logging.getLogger("bambu_inventory")

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
INVENTORY_COL_TOTAL = 3
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
                total_cell = match[INVENTORY_COL_TOTAL - 1]
                # Remaining Weight seeds from Total Weight the first time this
                # spool is used (i.e. Remaining is still blank) rather than
                # always starting from 0 - otherwise filling in Total Weight
                # after the fact never corrects an already-negative Remaining.
                if remaining_cell.value is None:
                    baseline = total_cell.value if total_cell.value is not None else 0
                else:
                    baseline = remaining_cell.value
                new_remaining = baseline - row["weight_g"]
                remaining_cell.value = new_remaining
                log.info(
                    f"Filament Inventory: {row['filament_type']} {row['colour_hex']} "
                    f"-{row['weight_g']}g -> {new_remaining}g remaining"
                )
            else:
                sheet.append([
                    row["filament_type"], row["colour_hex"], "", -row["weight_g"],
                ])
                log.info(
                    f"Filament Inventory: no matching row for {row['filament_type']} "
                    f"{row['colour_hex']}, added new row (-{row['weight_g']}g, "
                    f"fill in Total Weight (g) to track it properly)"
                )

        workbook.save(self._path)
