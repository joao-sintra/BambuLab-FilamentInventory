import os
from openpyxl import load_workbook
from bambu_inventory.local_sheet import LocalSheetWriter, HEADER, SHEET_NAME


def test_ensure_workbook_creates_file_with_header_when_missing(tmp_path):
    path = str(tmp_path / "inventory.xlsx")
    writer = LocalSheetWriter(path)

    result = writer.ensure_workbook()

    assert result == path
    assert os.path.exists(path)
    workbook = load_workbook(path)
    sheet = workbook[SHEET_NAME]
    assert [cell.value for cell in sheet[1]] == HEADER


def test_ensure_workbook_does_not_overwrite_existing_file(tmp_path):
    path = str(tmp_path / "inventory.xlsx")
    writer = LocalSheetWriter(path)
    writer.ensure_workbook()
    writer.append_rows([{
        "date": "2026-07-30T09:00:00Z", "print_name": "Vase", "printer": "X1C-A",
        "status": "finished", "duration_min": 30, "ams_slot": "0-1",
        "filament_type": "PLA", "colour_hex": "FF0000FF", "weight_g": 12.5,
        "task_id": "1002",
    }])

    writer2 = LocalSheetWriter(path)
    writer2.ensure_workbook()

    workbook = load_workbook(path)
    sheet = workbook[SHEET_NAME]
    assert sheet.max_row == 2


def test_append_rows_writes_values_in_header_order(tmp_path):
    path = str(tmp_path / "inventory.xlsx")
    writer = LocalSheetWriter(path)
    writer.ensure_workbook()
    row = {
        "date": "2026-07-30T09:00:00Z", "print_name": "Two Color Vase", "printer": "X1C-A",
        "status": "failed", "duration_min": 30, "ams_slot": "0-1",
        "filament_type": "PLA", "colour_hex": "FF0000FF", "weight_g": 12.5,
        "task_id": "1002",
    }

    writer.append_rows([row])

    workbook = load_workbook(path)
    sheet = workbook[SHEET_NAME]
    written = [cell.value for cell in sheet[2]]
    assert written == [
        "2026-07-30T09:00:00Z", "Two Color Vase", "X1C-A", "failed", 30,
        "0-1", "PLA", "FF0000FF", 12.5, "1002",
    ]


def test_append_rows_appends_multiple_calls_without_overwriting(tmp_path):
    path = str(tmp_path / "inventory.xlsx")
    writer = LocalSheetWriter(path)
    writer.ensure_workbook()
    row = {
        "date": "d", "print_name": "p", "printer": "pr", "status": "finished",
        "duration_min": 1, "ams_slot": "0-0", "filament_type": "PLA",
        "colour_hex": "000000FF", "weight_g": 1.0, "task_id": "1",
    }

    writer.append_rows([row])
    writer.append_rows([row])

    workbook = load_workbook(path)
    sheet = workbook[SHEET_NAME]
    assert sheet.max_row == 3
