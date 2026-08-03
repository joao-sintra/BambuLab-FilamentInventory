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
    assert is_terminal_status(1) is False


def test_is_terminal_status_true_for_finished_and_cancelled():
    assert is_terminal_status(2) is True
    assert is_terminal_status(3) is True


def test_is_terminal_status_false_for_unrecognized_intermediate_status():
    assert is_terminal_status(99) is False


def test_status_label_maps_known_values():
    assert status_label(2) == "finished"
    assert status_label(3) == "cancelled"


def test_status_label_returns_unknown_for_unrecognized_value():
    assert status_label(99) == "unknown"


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


def test_filter_new_terminal_tasks_handles_digit_length_rollover():
    tasks = [
        {
            "id": "100000000", "title": "New Print", "deviceName": "X1C-A",
            "status": 2, "startTime": "2026-08-01T00:00:00Z", "costTime": 60,
            "amsDetailMapping": [],
        }
    ]
    result = filter_new_terminal_tasks(tasks, last_seen_id="99999999")
    assert len(result) == 1


def test_task_to_rows_expands_multi_color_task():
    tasks = load_tasks()
    task = next(t for t in tasks if t["id"] == "1002")
    rows = task_to_rows(task)
    assert len(rows) == 2
    assert rows[0]["task_id"] == "1002"
    assert rows[0]["print_name"] == "Two Color Vase"
    assert rows[0]["status"] == "cancelled"
    assert rows[0]["duration_min"] == 30
    assert rows[0]["ams_slot"] == "0-1"
    assert rows[0]["filament_type"] == "PLA"
    assert rows[0]["colour_hex"] == "FF0000FF"
    # planned weight 8.0g scaled by elapsed/costTime = 450s/1800s = 0.25 -> 2.0g
    assert rows[0]["weight_g"] == 2.0
    assert rows[1]["ams_slot"] == "0-2"
    assert rows[1]["weight_g"] == 4.0


def test_task_to_rows_single_color_task():
    tasks = load_tasks()
    task = next(t for t in tasks if t["id"] == "1001")
    rows = task_to_rows(task)
    assert len(rows) == 1
    assert rows[0]["status"] == "finished"
    assert rows[0]["duration_min"] == 60
    # finished prints are never scaled, even though this fixture's
    # startTime/endTime elapsed (3600s) happens to equal costTime here
    assert rows[0]["weight_g"] == 20.0


def test_task_to_rows_does_not_scale_finished_print_weight_even_if_elapsed_time_is_short():
    task = {
        "id": "2001", "title": "Fast Finish", "deviceName": "X1C-A",
        "status": 2, "startTime": "2026-08-01T00:00:00Z",
        "endTime": "2026-08-01T00:01:00Z", "costTime": 3600,
        "amsDetailMapping": [{
            "amsId": 0, "slotId": 0, "filamentType": "PLA",
            "targetColor": "FFFFFFFF", "weight": 50.0,
        }],
    }
    rows = task_to_rows(task)
    assert rows[0]["weight_g"] == 50.0


def test_task_to_rows_scales_cancelled_print_weight_by_elapsed_ratio():
    task = {
        "id": "2002", "title": "Half Cancelled", "deviceName": "X1C-A",
        "status": 3, "startTime": "2026-08-01T00:00:00Z",
        "endTime": "2026-08-01T00:10:00Z", "costTime": 1200,
        "amsDetailMapping": [{
            "amsId": 0, "slotId": 0, "filamentType": "PLA",
            "targetColor": "FFFFFFFF", "weight": 400.0,
        }],
    }
    rows = task_to_rows(task)
    # elapsed 600s / costTime 1200s = 0.5 -> 200.0g
    assert rows[0]["weight_g"] == 200.0


def test_task_to_rows_falls_back_to_full_weight_when_cost_time_is_zero():
    task = {
        "id": "2003", "title": "Zero Cost Time", "deviceName": "X1C-A",
        "status": 3, "startTime": "2026-08-01T00:00:00Z",
        "endTime": "2026-08-01T00:00:05Z", "costTime": 0,
        "amsDetailMapping": [{
            "amsId": 0, "slotId": 0, "filamentType": "PLA",
            "targetColor": "FFFFFFFF", "weight": 10.0,
        }],
    }
    rows = task_to_rows(task)
    assert rows[0]["weight_g"] == 10.0


def test_task_to_rows_falls_back_to_full_weight_when_end_time_missing():
    task = {
        "id": "2004", "title": "No End Time", "deviceName": "X1C-A",
        "status": 3, "startTime": "2026-08-01T00:00:00Z", "costTime": 1200,
        "amsDetailMapping": [{
            "amsId": 0, "slotId": 0, "filamentType": "PLA",
            "targetColor": "FFFFFFFF", "weight": 10.0,
        }],
    }
    rows = task_to_rows(task)
    assert rows[0]["weight_g"] == 10.0
