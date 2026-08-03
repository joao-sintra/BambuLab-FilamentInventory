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
