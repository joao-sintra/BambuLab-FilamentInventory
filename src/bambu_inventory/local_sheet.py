from __future__ import annotations

import logging
import os

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

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


def _argb_from_bambu_hex(colour_hex: str) -> str | None:
    # Bambu's colour strings are RRGGBBAA; openpyxl wants ARGB (AARRGGBB).
    # A bare 6-char RRGGBB is treated as fully opaque.
    hex_only = "".join(c for c in colour_hex if c in "0123456789ABCDEFabcdef")
    if len(hex_only) == 8:
        rgb, alpha = hex_only[:6], hex_only[6:]
    elif len(hex_only) == 6:
        rgb, alpha = hex_only, "FF"
    else:
        return None
    return (alpha + rgb).upper()


def _contrast_font_argb(fill_argb: str) -> str:
    r, g, b = (int(fill_argb[i:i + 2], 16) for i in (2, 4, 6))
    # standard relative luminance for black/white text contrast
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "FF000000" if luminance > 0.6 else "FFFFFFFF"


def _apply_colour_swatch(cell, colour_hex: str) -> None:
    fill_argb = _argb_from_bambu_hex(colour_hex)
    if fill_argb is None:
        return
    cell.fill = PatternFill(fill_type="solid", fgColor=fill_argb)
    cell.font = Font(color=_contrast_font_argb(fill_argb))


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
        # Idempotency guard: if a poll cycle logs a task successfully but a
        # later step (e.g. sync_filament_inventory) fails before state
        # advances, the same task gets retried and would otherwise be
        # appended again on every retry. Skip any row whose Task ID already
        # appears in the sheet.
        workbook = load_workbook(self._path)
        sheet = workbook[SHEET_NAME]
        task_id_col = ROW_KEYS.index("task_id") + 1
        colour_col = ROW_KEYS.index("colour_hex") + 1
        existing_task_ids = {
            cell[0].value for cell in sheet.iter_rows(min_row=2, min_col=task_id_col, max_col=task_id_col)
        }
        for row in rows:
            if row["task_id"] in existing_task_ids:
                log.warning(f"PrintLog: task {row['task_id']} already logged, skipping duplicate row")
                continue
            sheet.append([row[key] for key in ROW_KEYS])
            _apply_colour_swatch(sheet.cell(row=sheet.max_row, column=colour_col), row["colour_hex"])
        workbook.save(self._path)

    def sync_filament_inventory(self, rows: list[dict]) -> None:
        # Remaining Weight is a live formula (Total - SUMIFS of matching
        # PrintLog rows), not a value this method computes and writes.
        # That way hand-editing a Weight (g) cell in PrintLog - or any other
        # PrintLog row - is reflected immediately, with no separate
        # "deduct" step to keep in sync.
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

            if match is None:
                sheet.append([row["filament_type"], row["colour_hex"], "", None])
                match = sheet[sheet.max_row]
                log.info(
                    f"Filament Inventory: added new row for {row['filament_type']} "
                    f"{row['colour_hex']}, fill in Total Weight (g) to track it"
                )

            _apply_colour_swatch(match[INVENTORY_COL_COLOUR - 1], row["colour_hex"])

            type_col = match[INVENTORY_COL_FILAMENT_TYPE - 1].coordinate
            colour_col = match[INVENTORY_COL_COLOUR - 1].coordinate
            total_col = match[INVENTORY_COL_TOTAL - 1].coordinate
            remaining_cell = match[INVENTORY_COL_REMAINING - 1]
            remaining_cell.value = (
                f"={total_col}-SUMIFS({SHEET_NAME}!I:I,{SHEET_NAME}!G:G,{type_col},"
                f"{SHEET_NAME}!H:H,{colour_col})"
            )

        workbook.save(self._path)
