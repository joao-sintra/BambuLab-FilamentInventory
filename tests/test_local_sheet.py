import os
from openpyxl import Workbook, load_workbook
from bambu_inventory.local_sheet import (
    LocalSheetWriter, HEADER, SHEET_NAME, INVENTORY_SHEET_NAME, INVENTORY_HEADER,
)


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


def _make_row(filament_type="PLA", colour_hex="FF0000FF", weight_g=10.0):
    return {
        "date": "d", "print_name": "p", "printer": "pr", "status": "finished",
        "duration_min": 1, "ams_slot": "0-0", "filament_type": filament_type,
        "colour_hex": colour_hex, "weight_g": weight_g, "task_id": "1",
    }


def test_deduct_filament_usage_subtracts_from_matching_row(tmp_path):
    path = str(tmp_path / "inventory.xlsx")
    workbook = Workbook()
    workbook.remove(workbook.active)
    sheet = workbook.create_sheet(INVENTORY_SHEET_NAME)
    sheet.append(INVENTORY_HEADER)
    sheet.append(["PLA", "FF0000FF", 1000, 500])
    workbook.save(path)

    writer = LocalSheetWriter(path)
    writer.deduct_filament_usage([_make_row(weight_g=12.5)])

    result = load_workbook(path)
    sheet = result[INVENTORY_SHEET_NAME]
    assert sheet.cell(row=2, column=4).value == 487.5


def test_deduct_filament_usage_creates_row_when_no_match(tmp_path):
    path = str(tmp_path / "inventory.xlsx")
    workbook = Workbook()
    workbook.remove(workbook.active)
    sheet = workbook.create_sheet(INVENTORY_SHEET_NAME)
    sheet.append(INVENTORY_HEADER)
    workbook.save(path)

    writer = LocalSheetWriter(path)
    writer.deduct_filament_usage([_make_row(filament_type="PETG", colour_hex="00FF00FF", weight_g=20.0)])

    result = load_workbook(path)
    sheet = result[INVENTORY_SHEET_NAME]
    assert sheet.max_row == 2
    new_row = [cell.value for cell in sheet[2]]
    assert new_row == ["PETG", "00FF00FF", None, -20.0]


def test_deduct_filament_usage_creates_inventory_sheet_if_missing(tmp_path):
    path = str(tmp_path / "inventory.xlsx")
    writer = LocalSheetWriter(path)
    writer.ensure_workbook()

    writer.deduct_filament_usage([_make_row(weight_g=5.0)])

    result = load_workbook(path)
    assert INVENTORY_SHEET_NAME in result.sheetnames
    sheet = result[INVENTORY_SHEET_NAME]
    assert [cell.value for cell in sheet[1]] == INVENTORY_HEADER
    assert [cell.value for cell in sheet[2]] == ["PLA", "FF0000FF", None, -5.0]


def test_deduct_filament_usage_matches_only_exact_type_and_colour(tmp_path):
    path = str(tmp_path / "inventory.xlsx")
    workbook = Workbook()
    workbook.remove(workbook.active)
    sheet = workbook.create_sheet(INVENTORY_SHEET_NAME)
    sheet.append(INVENTORY_HEADER)
    sheet.append(["PLA", "0000FFFF", 1000, 500])
    workbook.save(path)

    writer = LocalSheetWriter(path)
    writer.deduct_filament_usage([_make_row(filament_type="PLA", colour_hex="FF0000FF", weight_g=10.0)])

    result = load_workbook(path)
    sheet = result[INVENTORY_SHEET_NAME]
    assert sheet.max_row == 3
    assert sheet.cell(row=2, column=4).value == 500
    assert [cell.value for cell in sheet[3]] == ["PLA", "FF0000FF", None, -10.0]
